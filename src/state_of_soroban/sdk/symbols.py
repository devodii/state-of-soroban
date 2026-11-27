import io
import re
import tarfile

from pydantic import BaseModel

PUBLIC_FN = re.compile(
    r"^\s*pub(?:\([a-z]+\))?\s+(?:const\s+)?(?:unsafe\s+)?fn\s+(\w+)"
)
DEPRECATED = re.compile(r"#\[deprecated")
NOTE = re.compile(r'note\s*=\s*"((?:[^"\\]|\\.)*)"')
IMPL = re.compile(r"^impl(?:<[^>]*>)?\s+(?:[\w:<>,' ]+\s+for\s+)?(\w+)")
ITEM_START = re.compile(r"^\s*(pub\b|fn\b|impl\b|struct\b|enum\b|trait\b|mod\b|type\b)")


class Symbol(BaseModel):
    name: str
    deprecated: str | None


def parse_source(text: str, owners: set[str]) -> list[Symbol]:
    found: list[Symbol] = []
    pending: str | None = None
    collecting = False
    owner: str | None = None
    for line in text.splitlines():
        impl = IMPL.match(line)
        if impl:
            owner = impl.group(1)
        elif line.startswith("}"):
            owner = None
        if DEPRECATED.search(line):
            pending = ""
            collecting = True
        if collecting:
            note = NOTE.search(line)
            if note:
                pending = note.group(1)
            if "]" in line:
                collecting = False
                pending = pending or "deprecated"
            continue
        match = PUBLIC_FN.match(line)
        if match:
            if owner in owners:
                found.append(Symbol(name=match.group(1), deprecated=pending))
            pending = None
        elif ITEM_START.match(line):
            pending = None
    return found


def parse_crate(archive: bytes, owners: set[str]) -> list[Symbol]:
    symbols: dict[str, list[str | None]] = {}
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:gz") as tar:
        for member in tar.getmembers():
            parts = member.name.split("/")
            if not member.isfile() or len(parts) < 3 or parts[1] != "src":
                continue
            if not member.name.endswith(".rs") or "/tests" in member.name:
                continue
            body = tar.extractfile(member)
            if body is None:
                continue
            for symbol in parse_source(body.read().decode("utf-8", "replace"), owners):
                symbols.setdefault(symbol.name, []).append(symbol.deprecated)
    return [
        Symbol(
            name=name,
            deprecated=notes[0] if all(note is not None for note in notes) else None,
        )
        for name, notes in sorted(symbols.items())
    ]
