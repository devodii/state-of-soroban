import asyncio
import json
import logging
import re
from datetime import UTC, datetime

from state_of_soroban import checkpoints
from state_of_soroban.extract.ecosystem import Dep, package_index, parse_manifest
from state_of_soroban.github.client import GithubUnavailable
from state_of_soroban.resilience import NETWORK_ERRORS, until_online
from state_of_soroban.runner import Context, stage
from state_of_soroban.sql_loader import load_sql
from state_of_soroban.workflow import Stage

log = logging.getLogger("state_of_soroban")

JOB = "ecosystem"
BLOB = "... on Blob { text byteSize isTruncated }"
TREE = "... on Tree { entries { name type object { ... on Blob { text byteSize } } } }"
DOC_KINDS = {
    "readme": "readme",
    "contributing.md": "docs",
    "security.md": "security",
    "makefile": "build",
    "justfile": "build",
    "taskfile.yml": "build",
    "dockerfile": "docker",
    "docker-compose.yml": "docker",
    "docker-compose.yaml": "docker",
    ".env.example": "env",
    "stellar.toml": "toolchain",
    "soroban.json": "toolchain",
    ".tool-versions": "toolchain",
}


def lookups(context: Context) -> tuple[str, dict[str, tuple[str, str]]]:
    config = context.workflow.ecosystem
    fields: list[str] = [
        'root: object(expression: "HEAD:") { ... on Tree { entries { name type } } }'
    ]
    mapping: dict[str, tuple[str, str]] = {}

    def add(path: str, kind: str, shape: str) -> None:
        alias = f"f{len(mapping)}"
        mapping[alias] = (path, kind)
        fields.append(
            f"{alias}: object(expression: {json.dumps('HEAD:' + path)}) {{ {shape} }}"
        )

    for name in [*config.manifests, *config.files]:
        add(name, "blob", BLOB)
    for name in config.trees:
        add(name, "tree", TREE)
    return "\n".join(fields), mapping


def nested_fields(
    context: Context, directories: list[str]
) -> tuple[str, dict[str, tuple[str, str]]]:
    config = context.workflow.ecosystem
    fields: list[str] = []
    mapping: dict[str, tuple[str, str]] = {}
    for directory in directories:
        for name in config.nested_manifests:
            alias = f"n{len(mapping)}"
            path = f"{directory}/{name}"
            mapping[alias] = (path, "blob")
            fields.append(
                f"{alias}: object(expression: {json.dumps('HEAD:' + path)}) {{ {BLOB} }}"
            )
    return "\n".join(fields), mapping


def document_kind(path: str) -> str | None:
    name = path.rsplit("/", 1)[-1].lower()
    for key, kind in DOC_KINDS.items():
        if name == key or (key == "readme" and name.startswith("readme")):
            return kind
    return None


def collect(node: dict, mapping: dict, limit: int) -> dict[str, str]:
    files: dict[str, str] = {}
    for alias, (path, kind) in mapping.items():
        value = node.get(alias)
        if not value:
            continue
        if kind == "blob" and value.get("text"):
            files[path] = value["text"][:limit].replace("\x00", "")
        elif kind == "tree":
            for entry in value.get("entries") or []:
                blob = entry.get("object") or {}
                if entry["type"] == "blob" and blob.get("text"):
                    files[f"{path}/{entry['name']}"] = blob["text"][:limit].replace(
                        "\x00", ""
                    )
    return files


def repo_query(names: list[str], bodies: list[str]) -> str:
    return (
        "query {"
        + " ".join(
            f"r{i}: repository(owner: {json.dumps(n.split('/')[0])}, name: {json.dumps(n.split('/')[1])}) {{ nameWithOwner {bodies[i]} }}"
            for i, n in enumerate(names)
        )
        + "}"
    )


async def fetch_batch(
    context: Context, names: list[str], body: str, mapping: dict
) -> dict[str, dict[str, str]]:
    config = context.workflow.ecosystem
    limit = config.max_text_bytes
    data = await context.github.graphql(repo_query(names, [body] * len(names)))
    found: dict[str, dict[str, str]] = {}
    nested_names: list[str] = []
    nested_bodies: list[str] = []
    nested_maps: list[dict] = []
    for i, name in enumerate(names):
        node = data.get(f"r{i}") or {}
        found[name] = collect(node, mapping, limit)
        entries = (node.get("root") or {}).get("entries") or []
        directories = [
            e["name"]
            for e in entries
            if e["type"] == "tree" and e["name"] in config.subdirs
        ]
        if directories:
            fields, nested_map = nested_fields(context, directories)
            nested_names.append(name)
            nested_bodies.append(fields)
            nested_maps.append(nested_map)
    if nested_names:
        extra = await context.github.graphql(repo_query(nested_names, nested_bodies))
        for i, name in enumerate(nested_names):
            found[name].update(collect(extra.get(f"r{i}") or {}, nested_maps[i], limit))
    return found


def classify_file(path: str) -> str:
    if path.startswith((".github/workflows/", ".circleci/")):
        return "ci"
    if path.startswith("scripts/"):
        return "script"
    if path.rsplit("/", 1)[-1] in {
        "package.json",
        "requirements.txt",
        "pyproject.toml",
        "go.mod",
        "Cargo.toml",
        "composer.json",
        "Gemfile",
        "pubspec.yaml",
        "Package.swift",
        "build.gradle",
        "build.gradle.kts",
        "pom.xml",
        "Pipfile",
    }:
        return "manifest"
    return document_kind(path) or "other"


async def store(context: Context, name: str, files: dict[str, str]) -> None:
    config = context.workflow.ecosystem
    index = package_index(context.catalog.tools)
    terms = re.compile(config.stellar_terms, re.I)
    deps: list[Dep] = []
    for path, text in files.items():
        if classify_file(path) == "manifest":
            deps.extend(parse_manifest(path, text).deps)
    libs = sorted(
        {
            index[(d.ecosystem, d.name.lower())]
            for d in deps
            if (d.ecosystem, d.name.lower()) in index
        }
    )
    readme = next((t for p, t in files.items() if classify_file(p) == "readme"), "")
    stellar = (
        bool(libs)
        or any(terms.search(d.name) for d in deps)
        or bool(terms.search(readme[:20000]))
    )
    stack = sorted({d.ecosystem for d in deps})
    async with context.pool.acquire() as connection, connection.transaction():
        await connection.executemany(
            load_sql("ins_ecosystem_dep"),
            [(name, d.ecosystem, d.path, d.name, d.kind, d.requirement) for d in deps],
        )
        await connection.executemany(
            load_sql("ins_document"),
            [
                (name, path, classify_file(path), len(text), "graphql", text)
                for path, text in files.items()
            ],
        )
        await connection.execute(
            load_sql("update_ecosystem_repo"), name, stellar, stack, libs
        )


@stage("github.ecosystem")
async def ecosystem(context: Context, _: Stage) -> None:
    config = context.workflow.ecosystem
    cutoff = datetime.combine(
        context.workflow.window.start, datetime.min.time(), tzinfo=UTC
    )
    targets = [
        r["full_name"]
        for r in await context.pool.fetch(load_sql("ecosystem_targets"), cutoff)
    ]
    if context.limit:
        targets = targets[: context.limit]
    body, mapping = lookups(context)
    batches = [
        targets[i : i + config.batch] for i in range(0, len(targets), config.batch)
    ]
    gate = asyncio.Semaphore(config.concurrency)

    async def one(batch: list[str]) -> None:
        async with gate:
            while True:
                try:
                    found = await fetch_batch(context, batch, body, mapping)
                    break
                except NETWORK_ERRORS:
                    await until_online(context.http)
                except GithubUnavailable:
                    for name in batch:
                        await checkpoints.put(
                            context.pool, JOB, name, "failed", {}, "graphql unavailable"
                        )
                    context.errors += len(batch)
                    return
        for name, files in found.items():
            try:
                await store(context, name, files)
                context.items += 1
            except Exception as error:
                context.errors += 1
                await checkpoints.put(
                    context.pool, JOB, name, "failed", {}, str(error)[:200]
                )
        if context.items % 80 < config.batch:
            log.info(
                "ecosystem fingerprints for %s/%s repos", context.items, len(targets)
            )

    await asyncio.gather(*(one(b) for b in batches))
