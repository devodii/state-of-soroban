import json
import re
import tomllib
from pathlib import PurePosixPath

import yaml
from pydantic import BaseModel, Field


class Dep(BaseModel):
    ecosystem: str
    path: str
    name: str
    kind: str = "runtime"
    requirement: str | None = None


class Parsed(BaseModel):
    deps: list[Dep] = Field(default_factory=list)
    scripts: dict[str, str] = Field(default_factory=dict)


REQ_LINE = re.compile(
    r"^\s*([A-Za-z0-9_.\-]+)\s*(?:\[[^\]]*\])?\s*([<>=!~]=?[^;#\s]*)?"
)
GO_REQ = re.compile(r"^\s*([\w./~\-]+\.[\w./~\-]+)\s+(v[\w.\-+]+)", re.M)
GEM = re.compile(r"""^\s*gem\s+['"]([^'"]+)['"](?:\s*,\s*['"]([^'"]+)['"])?""", re.M)
SWIFT_PKG = re.compile(
    r"""\.package\(\s*(?:name:\s*"[^"]*",\s*)?url:\s*"([^"]+)"[^)]*?(?:from:\s*"([^"]+)")?"""
)
GRADLE = re.compile(
    r"""(?:implementation|api|compileOnly|runtimeOnly|testImplementation|classpath)\s*\(?\s*["']([^"':]+:[^"':]+)(?::([^"']+))?["']"""
)
POM = re.compile(
    r"<dependency>\s*<groupId>([^<]+)</groupId>\s*<artifactId>([^<]+)</artifactId>(?:\s*<version>([^<]+)</version>)?",
    re.S,
)


def package_json(path: str, text: str) -> Parsed:
    try:
        data = json.loads(text)
    except ValueError:
        return Parsed()
    parsed = Parsed()
    for table, kind in (
        ("dependencies", "runtime"),
        ("devDependencies", "dev"),
        ("peerDependencies", "peer"),
        ("optionalDependencies", "optional"),
    ):
        for name, version in (data.get(table) or {}).items():
            parsed.deps.append(
                Dep(
                    ecosystem="npm",
                    path=path,
                    name=name,
                    kind=kind,
                    requirement=str(version),
                )
            )
    parsed.scripts = {
        str(k): str(v)[:400] for k, v in (data.get("scripts") or {}).items()
    }
    return parsed


def requirements(path: str, text: str) -> Parsed:
    parsed = Parsed()
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith(("#", "-", "git+", "http")):
            continue
        match = REQ_LINE.match(line)
        if match:
            parsed.deps.append(
                Dep(
                    ecosystem="pip",
                    path=path,
                    name=match.group(1),
                    requirement=match.group(2),
                )
            )
    return parsed


def pyproject(path: str, text: str) -> Parsed:
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError:
        return Parsed()
    parsed = Parsed()
    for spec in data.get("project", {}).get("dependencies") or []:
        match = REQ_LINE.match(spec)
        if match:
            parsed.deps.append(
                Dep(
                    ecosystem="pip",
                    path=path,
                    name=match.group(1),
                    requirement=match.group(2),
                )
            )
    for name, version in (
        data.get("tool", {}).get("poetry", {}).get("dependencies") or {}
    ).items():
        if name.lower() != "python":
            parsed.deps.append(
                Dep(
                    ecosystem="pip", path=path, name=name, requirement=str(version)[:60]
                )
            )
    for group in (data.get("dependency-groups") or {}).values():
        for spec in group:
            if isinstance(spec, str):
                match = REQ_LINE.match(spec)
                if match:
                    parsed.deps.append(
                        Dep(
                            ecosystem="pip",
                            path=path,
                            name=match.group(1),
                            kind="dev",
                            requirement=match.group(2),
                        )
                    )
    return parsed


def go_mod(path: str, text: str) -> Parsed:
    return Parsed(
        deps=[
            Dep(ecosystem="go", path=path, name=m.group(1), requirement=m.group(2))
            for m in GO_REQ.finditer(text)
        ]
    )


def cargo(path: str, text: str) -> Parsed:
    from state_of_soroban.extract.manifest import parse_cargo

    info = parse_cargo(path, text)
    if info is None:
        return Parsed()
    return Parsed(
        deps=[
            Dep(
                ecosystem="cargo",
                path=path,
                name=d.name,
                kind=d.kind,
                requirement=d.requirement,
            )
            for d in info.dependencies
        ]
    )


def composer(path: str, text: str) -> Parsed:
    try:
        data = json.loads(text)
    except ValueError:
        return Parsed()
    parsed = Parsed()
    for table, kind in (("require", "runtime"), ("require-dev", "dev")):
        for name, version in (data.get(table) or {}).items():
            if "/" in name:
                parsed.deps.append(
                    Dep(
                        ecosystem="composer",
                        path=path,
                        name=name,
                        kind=kind,
                        requirement=str(version),
                    )
                )
    return parsed


def gemfile(path: str, text: str) -> Parsed:
    return Parsed(
        deps=[
            Dep(ecosystem="gem", path=path, name=m.group(1), requirement=m.group(2))
            for m in GEM.finditer(text)
        ]
    )


def pubspec(path: str, text: str) -> Parsed:
    try:
        data = yaml.safe_load(text) or {}
    except yaml.YAMLError:
        return Parsed()
    parsed = Parsed()
    for table, kind in (("dependencies", "runtime"), ("dev_dependencies", "dev")):
        for name, version in (data.get(table) or {}).items():
            parsed.deps.append(
                Dep(
                    ecosystem="pub",
                    path=path,
                    name=name,
                    kind=kind,
                    requirement=str(version)[:60],
                )
            )
    return parsed


def swift(path: str, text: str) -> Parsed:
    return Parsed(
        deps=[
            Dep(
                ecosystem="swift",
                path=path,
                name=PurePosixPath(m.group(1).removesuffix(".git")).name,
                requirement=m.group(2),
            )
            for m in SWIFT_PKG.finditer(text)
        ]
    )


def gradle(path: str, text: str) -> Parsed:
    return Parsed(
        deps=[
            Dep(ecosystem="gradle", path=path, name=m.group(1), requirement=m.group(2))
            for m in GRADLE.finditer(text)
        ]
    )


def pom(path: str, text: str) -> Parsed:
    return Parsed(
        deps=[
            Dep(
                ecosystem="maven",
                path=path,
                name=f"{m.group(1).strip()}:{m.group(2).strip()}",
                requirement=m.group(3),
            )
            for m in POM.finditer(text)
        ]
    )


PARSERS = {
    "package.json": package_json,
    "requirements.txt": requirements,
    "pyproject.toml": pyproject,
    "Pipfile": lambda p, t: Parsed(),
    "go.mod": go_mod,
    "Cargo.toml": cargo,
    "composer.json": composer,
    "Gemfile": gemfile,
    "pubspec.yaml": pubspec,
    "Package.swift": swift,
    "build.gradle": gradle,
    "build.gradle.kts": gradle,
    "pom.xml": pom,
}


def parse_manifest(path: str, text: str) -> Parsed:
    parser = PARSERS.get(PurePosixPath(path).name)
    if parser is None:
        return Parsed()
    try:
        return parser(path, text)
    except Exception:
        return Parsed()


def package_index(tools: list) -> dict[tuple[str, str], str]:
    found: dict[tuple[str, str], str] = {}
    for tool in tools:
        for ecosystem, names in tool.packages.items():
            for name in names:
                found[(ecosystem, name.lower())] = tool.id
    return found
