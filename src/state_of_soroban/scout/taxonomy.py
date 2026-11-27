import asyncio
import re
from pathlib import Path

from pydantic import BaseModel

ADD = re.compile(r'^repadd\s+"?Stellar"?\s+(\S+)', re.IGNORECASE)
REMOVE = re.compile(r'^reprem\s+"?Stellar"?\s+(\S+)', re.IGNORECASE)


class Taxonomy(BaseModel):
    listed: set[str]
    removed: set[str]


def normalise(url: str) -> str:
    return url.lower().rstrip("/")


async def refresh(remote: str, cache: Path) -> None:
    if (cache / ".git").exists():
        command = ["git", "-C", str(cache), "pull", "--ff-only", "--depth", "1", "-q"]
    else:
        cache.parent.mkdir(parents=True, exist_ok=True)
        command = ["git", "clone", "--depth", "1", "-q", remote, str(cache)]
    process = await asyncio.create_subprocess_exec(*command)
    if await process.wait() != 0:
        raise RuntimeError(f"could not refresh {remote}")


def read_taxonomy(cache: Path) -> Taxonomy:
    added: set[str] = set()
    removed: set[str] = set()
    for path in sorted((cache / "migrations").iterdir()):
        for line in path.read_text(errors="ignore").splitlines():
            text = line.strip()
            if match := ADD.match(text):
                added.add(normalise(match.group(1)))
            elif match := REMOVE.match(text):
                removed.add(normalise(match.group(1)))
    return Taxonomy(listed=added - removed, removed=removed)
