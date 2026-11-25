import json
import re
import tomllib
from pathlib import Path, PurePosixPath

from pydantic import BaseModel, Field

from state_of_soroban.catalog import BugClass, Catalog, Pattern
from state_of_soroban.extract.git import CommitRecord, TreeEntry
from state_of_soroban.extract.manifest import CrateInfo, parse_cargo, parse_lock
from state_of_soroban.extract.matcher import Hit, compiled, run_patterns
from state_of_soroban.extract.networks import NetworkHit, network_hits, network_of_ref
from state_of_soroban.extract.rust import ParsedFile, parse_rust
from state_of_soroban.extract.strkey import find_contract_ids
from state_of_soroban.workflow import Workflow

CLIENT_CALL = re.compile(r"\b([A-Z]\w*Client)::new\(\s*&?\w+\s*,\s*(&?[^)]+?)\)")
INVOKE_CALL = re.compile(
    r"\.invoke_contract(?:::<[^>]+>)?\(\s*(&?[^,]+),\s*&?"
    r"(?:symbol_short!\(\s*\"([^\"]+)\"|Symbol::new\(\s*&?\w+,\s*\"([^\"]+)\")"
)
IMPORT_CALL = re.compile(r"contractimport!\s*\(\s*file\s*=\s*\"([^\"]+)\"")
SOROBAN_MARK = re.compile(r"soroban[_-]sdk")
LOCKS = {"package-lock.json", "pnpm-lock.yaml", "yarn.lock", "Cargo.lock"}


class CallSite(BaseModel):
    start_byte: int
    line: int
    caller_fn: str | None
    kind: str
    callee: str | None
    method: str | None
    target: str | None


class SourceRecord(BaseModel):
    path: str
    crate_path: str | None
    blob_sha: str
    size: int
    parsed: ParsedFile
    content: str
    hits: list[Hit] = Field(default_factory=list)
    calls: list[CallSite] = Field(default_factory=list)


class DocumentRecord(BaseModel):
    path: str
    kind: str
    size: int
    blob_sha: str
    text: str | None


class RefRecord(BaseModel):
    path: str
    contract_id: str
    line: int
    network: str


class CommitTouch(BaseModel):
    sha: str
    pattern: str
    added: int
    removed: int


class Analysis(BaseModel):
    is_soroban: bool = False
    crates: list[CrateInfo] = Field(default_factory=list)
    locked_versions: dict[str, str] = Field(default_factory=dict)
    sources: list[SourceRecord] = Field(default_factory=list)
    documents: list[DocumentRecord] = Field(default_factory=list)
    network_signals: list[tuple[str, NetworkHit]] = Field(default_factory=list)
    refs: list[RefRecord] = Field(default_factory=list)
    commits: list[CommitRecord] = Field(default_factory=list)
    fix_shas: set[str] = Field(default_factory=set)
    bug_classes: dict[str, list[str]] = Field(default_factory=dict)
    touches: list[CommitTouch] = Field(default_factory=list)

    @property
    def networks(self) -> list[str]:
        return sorted({hit.network for _, hit in self.network_signals})


def glob_regex(glob: str) -> re.Pattern[str]:
    body = ""
    index = 0
    while index < len(glob):
        if glob.startswith("**/", index):
            body += "(?:.*/)?"
            index += 3
        elif glob.startswith("**", index):
            body += ".*"
            index += 2
        elif glob[index] == "*":
            body += "[^/]*"
            index += 1
        elif glob[index] == "?":
            body += "[^/]"
            index += 1
        else:
            body += re.escape(glob[index])
            index += 1
    return re.compile(f"^{body}$")


def sparse_patterns(workflow: Workflow) -> list[str]:
    clone = workflow.clone
    patterns = [f"*{suffix}" for suffix in clone.rust_suffixes]
    patterns += list(clone.manifests)
    patterns += [f"*{suffix}" for suffix in clone.signal_suffixes if suffix != ".json"]
    for kind in workflow.documents.kinds.values():
        patterns += kind.globs
    excluded = {f"!{name}" for name in LOCKS - {"Cargo.lock"}}
    excluded |= {f"!{name}/" for name in clone.skip_directories}
    return [*dict.fromkeys(patterns), *sorted(excluded)]


def crate_of(path: str, crates: list[CrateInfo]) -> str | None:
    best: str | None = None
    for crate in crates:
        base = "" if crate.path == "." else crate.path + "/"
        if path.startswith(base) and (best is None or len(crate.path) > len(best)):
            best = crate.path
    return best


def call_sites(parsed: ParsedFile) -> list[CallSite]:
    sites: list[CallSite] = []
    text = parsed.clean
    for match in CLIENT_CALL.finditer(text):
        line = text.count("\n", 0, match.start()) + 1
        function = parsed.function_at(line)
        sites.append(
            CallSite(
                start_byte=len(text[: match.start()].encode()),
                line=line,
                caller_fn=function.name if function else None,
                kind="client",
                callee=match.group(1),
                method=None,
                target=match.group(2).strip()[:160],
            )
        )
    for match in INVOKE_CALL.finditer(text):
        line = text.count("\n", 0, match.start()) + 1
        function = parsed.function_at(line)
        sites.append(
            CallSite(
                start_byte=len(text[: match.start()].encode()),
                line=line,
                caller_fn=function.name if function else None,
                kind="invoke",
                callee=None,
                method=match.group(2) or match.group(3),
                target=match.group(1).strip()[:160],
            )
        )
    for match in IMPORT_CALL.finditer(text):
        line = text.count("\n", 0, match.start()) + 1
        function = parsed.function_at(line)
        sites.append(
            CallSite(
                start_byte=len(text[: match.start()].encode()),
                line=line,
                caller_fn=function.name if function else None,
                kind="import",
                callee=None,
                method=None,
                target=match.group(1),
            )
        )
    return sites


def read_text(root: Path, entry: TreeEntry, limit: int) -> str | None:
    if entry.size > limit or entry.size == 0:
        return None
    try:
        return (root / entry.path).read_text(errors="replace").replace("\x00", "")
    except OSError:
        return None


def classify_documents(
    workflow: Workflow, entries: list[TreeEntry], root: Path
) -> list[DocumentRecord]:
    kinds = {
        name: [glob_regex(g) for g in kind.globs]
        for name, kind in workflow.documents.kinds.items()
    }
    limit = workflow.documents.max_text_bytes
    found: list[DocumentRecord] = []
    for entry in entries:
        kind = next(
            (
                name
                for name, patterns in kinds.items()
                if any(
                    p.match(entry.path) or p.match(PurePosixPath(entry.path).name)
                    for p in patterns
                )
            ),
            None,
        )
        if kind is None:
            continue
        textual = PurePosixPath(entry.path).suffix.lower() in {
            "",
            ".md",
            ".txt",
            ".yml",
            ".yaml",
            ".toml",
            ".json",
            ".rst",
        }
        found.append(
            DocumentRecord(
                path=entry.path,
                kind=kind,
                size=entry.size,
                blob_sha=entry.blob_sha,
                text=read_text(root, entry, limit) if textual else None,
            )
        )
    return found


def classify_message(message: str, bugs: list[BugClass]) -> list[str]:
    return [b.id for b in bugs if compiled(b.keywords).search(message)]


def touches_for(
    patterns: list[Pattern], patches: dict[str, list[str]]
) -> list[CommitTouch]:
    touches: list[CommitTouch] = []
    rules = [(p.id, compiled(p.diff)) for p in patterns if p.diff]
    for sha, lines in patches.items():
        for pattern_id, rule in rules:
            added = sum(
                1 for line in lines if line.startswith("+") and rule.search(line)
            )
            removed = sum(
                1 for line in lines if line.startswith("-") and rule.search(line)
            )
            if added or removed:
                touches.append(
                    CommitTouch(
                        sha=sha, pattern=pattern_id, added=added, removed=removed
                    )
                )
    return touches


def analyse_tree(
    root: Path,
    entries: list[TreeEntry],
    workflow: Workflow,
    catalog: Catalog,
    patterns: list[Pattern],
) -> Analysis:
    analysis = Analysis()
    clone = workflow.clone
    manifests = sorted(
        (e for e in entries if PurePosixPath(e.path).name == "Cargo.toml"),
        key=lambda e: e.path.count("/"),
    )
    workspace: dict[str, object] = {}
    for entry in manifests:
        text = read_text(root, entry, clone.max_file_bytes)
        info = parse_cargo(entry.path, text, workspace) if text else None
        if info is None:
            continue
        if info.is_workspace_root:
            try:
                workspace.update(
                    tomllib.loads(text).get("workspace", {}).get("dependencies", {})
                )
            except tomllib.TOMLDecodeError:
                pass
        analysis.crates.append(info)
    locks = [e for e in entries if PurePosixPath(e.path).name == "Cargo.lock"]
    for entry in sorted(locks, key=lambda e: e.path.count("/")):
        text = read_text(root, entry, 8_000_000)
        if text:
            for name, version in parse_lock(text).items():
                analysis.locked_versions.setdefault(name, version)
    sdk_locked = analysis.locked_versions.get("soroban-sdk")
    rust_entries = [
        e
        for e in entries
        if e.path.endswith(tuple(clone.rust_suffixes))
        and e.size <= clone.max_file_bytes
    ][: clone.max_rust_files]
    soroban_crates = any(c.depends_on("soroban-sdk") for c in analysis.crates)
    texts: dict[str, str] = {}
    for entry in rust_entries:
        text = read_text(root, entry, clone.max_file_bytes)
        if text is not None:
            texts[entry.path] = text
    analysis.is_soroban = (
        soroban_crates
        or "soroban-sdk" in analysis.locked_versions
        or any(SOROBAN_MARK.search(t) for t in texts.values())
    )
    if not analysis.is_soroban:
        return analysis
    for entry in rust_entries:
        text = texts.get(entry.path)
        if text is None:
            continue
        parsed = parse_rust(entry.path, text.encode())
        record = SourceRecord(
            path=entry.path,
            crate_path=crate_of(entry.path, analysis.crates),
            blob_sha=entry.blob_sha,
            size=entry.size,
            parsed=parsed,
            content=text,
            hits=run_patterns(patterns, parsed),
            calls=call_sites(parsed),
        )
        record.parsed.clean = ""
        if parsed.is_test and not clone.keep_test_content:
            record.content = ""
        analysis.sources.append(record)
    analysis.documents = classify_documents(workflow, entries, root)
    signal_suffixes = tuple(clone.signal_suffixes)
    scanned = 0
    seen_hits: dict[str, list[NetworkHit]] = {}
    pending_refs: list[tuple[str, str, int]] = []
    for entry in entries:
        name = PurePosixPath(entry.path).name
        if name in LOCKS or not (
            entry.path.endswith(signal_suffixes) or name.startswith(".env")
        ):
            continue
        if scanned >= clone.max_signal_files:
            break
        text = texts.get(entry.path) or read_text(root, entry, clone.max_file_bytes)
        if text is None:
            continue
        scanned += 1
        hits = network_hits(text, workflow.networks_signals)
        if hits:
            seen_hits[entry.path] = hits
            analysis.network_signals.extend((entry.path, h) for h in hits)
        for contract_id, line in find_contract_ids(text):
            pending_refs.append((entry.path, contract_id, line))
    repo_networks = set(analysis.networks)
    for path, contract_id, line in pending_refs:
        analysis.refs.append(
            RefRecord(
                path=path,
                contract_id=contract_id,
                line=line,
                network=network_of_ref(line, seen_hits.get(path, []), repo_networks),
            )
        )
    for crate in analysis.crates:
        if crate.depends_on("soroban-sdk"):
            crate.soroban_sdk_resolved = sdk_locked
    return analysis


def catalog_hash(patterns: list[Pattern]) -> str:
    from state_of_soroban.extract.rust import digest

    return digest(
        json.dumps([p.model_dump() for p in sorted(patterns, key=lambda p: p.id)])
    )
