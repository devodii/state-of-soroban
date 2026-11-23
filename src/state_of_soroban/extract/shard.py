import asyncio
import gzip
import itertools
import logging
import shutil
import tempfile
from pathlib import Path

from state_of_soroban.catalog import Pattern, load_catalog
from state_of_soroban.config import get_settings
from state_of_soroban.extract import git
from state_of_soroban.extract.analyse import (
    analyse_tree,
    catalog_hash,
    sparse_patterns,
)
from state_of_soroban.extract.shard_line import ShardLine
from state_of_soroban.stages.extract import read_history
from state_of_soroban.workflow import load_workflow

log = logging.getLogger("state_of_soroban")


def read_targets(path: Path, index: int, count: int) -> list[str]:
    names = [line.strip() for line in path.read_text().splitlines() if line.strip()]
    return names[index::count]


async def run_shard(
    targets: Path,
    patterns_file: Path,
    index: int,
    count: int,
    out: Path,
    concurrency: int,
) -> int:
    workflow = load_workflow()
    catalog = load_catalog(workflow)
    patterns = [
        Pattern.model_validate(item)
        for item in __import__("json").loads(patterns_file.read_text())
    ]
    digest = catalog_hash(patterns)
    names = read_targets(targets, index, count)
    since = workflow.window.start.isoformat()
    sparse = sparse_patterns(workflow)
    tokens = itertools.cycle(get_settings().github_tokens or [None])
    base = Path(tempfile.mkdtemp(prefix="sw-shard-"))
    out.parent.mkdir(parents=True, exist_ok=True)
    gate = asyncio.Semaphore(concurrency)
    lock = asyncio.Lock()
    done = 0

    with gzip.open(out, "wt", encoding="utf-8") as sink:

        async def emit(line: ShardLine) -> None:
            nonlocal done
            async with lock:
                sink.write(line.model_dump_json() + "\n")
                done += 1
                if done % 25 == 0 or done == len(names):
                    log.info("shard %s: %s/%s repos", index, done, len(names))

        async def one(name: str) -> None:
            destination = base / name.replace("/", "__")
            async with gate:
                try:
                    await git.clone(name, destination, since, next(tokens), sparse)
                    entries = await git.tracked_files(destination)
                    analysis = await asyncio.to_thread(
                        analyse_tree, destination, entries, workflow, catalog, patterns
                    )
                    if analysis.is_soroban:
                        await read_history(
                            workflow, catalog, destination, analysis, patterns
                        )
                    await emit(ShardLine(repo=name, digest=digest, analysis=analysis))
                except git.GitFailed as error:
                    text = str(error)
                    gone = (
                        "not found" in text.lower() or "access denied" in text.lower()
                    )
                    await emit(
                        ShardLine(repo=name, digest=digest, error=text[:200], gone=gone)
                    )
                except Exception as error:
                    await emit(
                        ShardLine(repo=name, digest=digest, error=str(error)[:200])
                    )
                finally:
                    shutil.rmtree(destination, ignore_errors=True)

        await asyncio.gather(*(one(name) for name in names))
    shutil.rmtree(base, ignore_errors=True)
    return len(names)
