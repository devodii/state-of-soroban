import asyncio
import itertools
import logging
import shutil
import tempfile
from datetime import UTC, datetime
from pathlib import Path

import asyncpg

from state_of_soroban import checkpoints
from state_of_soroban.catalog import Catalog, active_patterns
from state_of_soroban.config import get_settings
from state_of_soroban.extract import git
from state_of_soroban.extract.analyse import (
    Analysis,
    analyse_tree,
    catalog_hash,
    classify_message,
    sparse_patterns,
    touches_for,
)
from state_of_soroban.extract.matcher import compiled
from state_of_soroban.runner import Context, stage
from state_of_soroban.sql_loader import load_sql
from state_of_soroban.workflow import Stage, Workflow

log = logging.getLogger("state_of_soroban")

MAX_PATCHED_COMMITS = 150


async def read_history(
    workflow: Workflow,
    catalog: Catalog,
    root: Path,
    analysis: Analysis,
    patterns: list,
) -> None:
    window = workflow.window
    history = workflow.history
    if history.commits == "none":
        return
    commits = await git.commit_log(
        root, window.start.isoformat(), window.end.isoformat()
    )
    fix = compiled(history.fix_message)
    for commit in commits:
        classes = classify_message(commit.message, catalog.bug_classes)
        analysis.bug_classes[commit.sha] = classes
        if fix.search(commit.message):
            analysis.fix_shas.add(commit.sha)
    if history.commits == "fixes":
        commits = [c for c in commits if c.sha in analysis.fix_shas]
    analysis.commits = commits
    fixes = [c for c in commits if c.sha in analysis.fix_shas][:MAX_PATCHED_COMMITS]
    if history.commit_files and fixes:
        files = await git.commit_files(root, [c.sha for c in fixes])
        for commit in fixes:
            commit.files = files.get(commit.sha, [])
    rusty = [
        c.sha
        for c in fixes
        if c.parents == 1 and any(f.path.endswith(".rs") for f in c.files)
    ]
    if rusty:
        patches = await git.rust_patches(root, rusty)
        analysis.touches = touches_for(patterns, patches)


async def store(
    connection: asyncpg.Connection, repo: str, analysis: Analysis, digest: str
) -> None:
    async with connection.transaction():
        await connection.execute(load_sql("clear_repo_scan"), repo)
        rust_loc = sum(s.parsed.loc for s in analysis.sources)
        contract_crates = sum(1 for c in analysis.crates if c.is_contract)
        if analysis.is_soroban:
            await connection.executemany(
                load_sql("ins_crate"),
                [
                    (
                        repo,
                        c.path,
                        c.name,
                        c.version,
                        c.edition,
                        c.is_workspace_root,
                        c.workspace_members,
                        c.is_contract,
                        c.crate_types,
                        c.soroban_sdk_requirement,
                        c.soroban_sdk_resolved,
                        c.features,
                        c.profiles,
                        c.metadata,
                    )
                    for c in analysis.crates
                ],
            )
            await connection.executemany(
                load_sql("ins_dependency"),
                [
                    (
                        repo,
                        c.path,
                        d.kind,
                        d.name,
                        d.requirement,
                        d.source,
                        d.git_url,
                        d.local_path,
                        d.features,
                        d.optional,
                    )
                    for c in analysis.crates
                    for d in c.dependencies
                ],
            )
            await connection.executemany(
                load_sql("ins_source_file"),
                [
                    (
                        repo,
                        s.path,
                        s.crate_path,
                        s.blob_sha,
                        s.size,
                        s.parsed.loc,
                        s.parsed.is_test,
                        s.parsed.parse_errors,
                        s.content,
                        digest,
                        s.parsed.uses,
                        sorted(
                            {
                                *s.parsed.macros,
                                *(m for f in s.parsed.functions for m in f.macros),
                            }
                        ),
                    )
                    for s in analysis.sources
                ],
            )
            await connection.executemany(
                load_sql("ins_function"),
                [
                    (
                        repo,
                        s.path,
                        f.line_start,
                        f.name,
                        f.line_end,
                        f.loc,
                        f.impl_type,
                        f.trait_name,
                        f.visibility,
                        f.attributes,
                        [p.model_dump() for p in f.params],
                        f.return_type,
                        f.is_contract_fn,
                        f.is_test,
                        f.body_hash,
                        f.shape_hash,
                        f.shape_nodes,
                        f.calls,
                        f.macros,
                    )
                    for s in analysis.sources
                    for f in s.parsed.functions
                ],
            )
            await connection.executemany(
                load_sql("ins_type_def"),
                [
                    (
                        repo,
                        s.path,
                        t.line_start,
                        t.name,
                        t.kind,
                        t.attributes,
                        t.derives,
                        t.is_contracttype,
                        t.is_contracterror,
                        t.is_contractevent,
                        [m.model_dump() for m in t.members],
                        t.shape_hash,
                    )
                    for s in analysis.sources
                    for t in s.parsed.types
                ],
            )
            await connection.executemany(
                load_sql("ins_pattern_match"),
                [
                    (
                        repo,
                        s.path,
                        h.pattern,
                        h.start_byte,
                        h.line_start,
                        h.line_end,
                        h.fn_name,
                        h.in_test,
                        h.snippet,
                        h.shape_hash,
                        h.captures,
                    )
                    for s in analysis.sources
                    for h in s.hits
                ],
            )
            await connection.executemany(
                load_sql("ins_contract_call"),
                [
                    (
                        repo,
                        s.path,
                        c.start_byte,
                        c.line,
                        c.caller_fn,
                        c.kind,
                        c.callee,
                        c.method,
                        c.target,
                    )
                    for s in analysis.sources
                    for c in s.calls
                ],
            )
            await connection.executemany(
                load_sql("ins_document"),
                [
                    (repo, d.path, d.kind, d.size, d.blob_sha, d.text)
                    for d in analysis.documents
                ],
            )
            await connection.executemany(
                load_sql("ins_network_signal"),
                [
                    (repo, path, h.network, h.signal, h.line, h.evidence)
                    for path, h in analysis.network_signals
                ],
            )
            await connection.executemany(
                load_sql("ins_contract_ref"),
                [
                    (repo, r.path, r.contract_id, r.network, r.line)
                    for r in analysis.refs
                ],
            )
            await connection.executemany(
                load_sql("ins_commit"),
                [
                    (
                        repo,
                        c.sha,
                        c.author_login,
                        c.author_name,
                        c.committed_at,
                        c.message,
                        c.parents,
                        len(c.files),
                        any(f.path.endswith(".rs") for f in c.files),
                        c.sha in analysis.fix_shas,
                        analysis.bug_classes.get(c.sha, []),
                    )
                    for c in analysis.commits
                ],
            )
            await connection.executemany(
                load_sql("ins_commit_file"),
                [
                    (repo, c.sha, f.path, f.status, f.previous_path)
                    for c in analysis.commits
                    for f in c.files
                ],
            )
            known = {c.sha for c in analysis.commits}
            await connection.executemany(
                load_sql("ins_commit_touch"),
                [
                    (repo, t.sha, t.pattern, t.added, t.removed)
                    for t in analysis.touches
                    if t.sha in known
                ],
            )
            people: dict[str, list] = {}
            for commit in analysis.commits:
                key = commit.author_login or f"name:{commit.author_name}"
                entry = people.setdefault(
                    key, [0, commit.committed_at, commit.committed_at]
                )
                entry[0] += 1
                entry[1] = min(entry[1], commit.committed_at)
                entry[2] = max(entry[2], commit.committed_at)
            await connection.executemany(
                load_sql("ins_contributor"),
                [
                    (repo, login, n, first, last)
                    for login, (n, first, last) in people.items()
                ],
            )
        await connection.execute(
            load_sql("mark_scanned"),
            repo,
            analysis.is_soroban,
            analysis.networks,
            analysis.locked_versions,
            len(analysis.sources),
            rust_loc,
            contract_crates,
        )


@stage("git.extract")
async def extract(context: Context, _: Stage) -> None:
    workflow = context.workflow
    clone = workflow.clone
    since = workflow.window.start.isoformat()
    cutoff = datetime.combine(workflow.window.start, datetime.min.time(), tzinfo=UTC)
    async with context.pool.acquire() as connection:
        targets = [
            row["full_name"]
            for row in await connection.fetch(
                load_sql("scan_targets"),
                cutoff,
                clone.require_language or "",
                clone.max_repo_kb,
                context.force,
            )
        ]
    if context.limit:
        targets = targets[: context.limit]
    patterns = await active_patterns(context.pool, context.catalog)
    digest = catalog_hash(patterns)
    sparse = sparse_patterns(workflow)
    tokens = itertools.cycle(get_settings().github_tokens or [None])
    base = get_settings().clone_dir or Path(tempfile.mkdtemp(prefix="sw-clones-"))
    base.mkdir(parents=True, exist_ok=True)
    gate = asyncio.Semaphore(clone.concurrency)
    soroban = 0

    async def one(name: str) -> None:
        nonlocal soroban
        destination = base / name.replace("/", "__")
        async with gate:
            try:
                await git.clone(name, destination, since, next(tokens), sparse)
                entries = await git.tracked_files(destination)
                analysis = await asyncio.to_thread(
                    analyse_tree,
                    destination,
                    entries,
                    workflow,
                    context.catalog,
                    patterns,
                )
                if analysis.is_soroban:
                    await read_history(
                        workflow, context.catalog, destination, analysis, patterns
                    )
                async with context.pool.acquire() as connection:
                    await store(connection, name, analysis, digest)
                soroban += analysis.is_soroban
            except git.GitFailed as error:
                context.errors += 1
                gone = (
                    "not found" in str(error).lower()
                    or "access denied" in str(error).lower()
                )
                await checkpoints.put(
                    context.pool,
                    "extract",
                    name,
                    "gone" if gone else "failed",
                    {},
                    str(error)[:200],
                )
                log.warning("skipped %s: %s", name, str(error)[:160])
            except Exception as error:
                context.errors += 1
                await checkpoints.put(
                    context.pool, "extract", name, "failed", {}, str(error)[:200]
                )
                log.exception("failed on %s", name)
            finally:
                if not clone.keep:
                    shutil.rmtree(destination, ignore_errors=True)
        context.items += 1
        if context.items % 25 == 0 or context.items == len(targets):
            log.info(
                "extracted %s/%s repos, %s soroban, %s errors",
                context.items,
                len(targets),
                soroban,
                context.errors,
            )

    await asyncio.gather(*(one(name) for name in targets))
    context.detail["soroban"] = soroban
