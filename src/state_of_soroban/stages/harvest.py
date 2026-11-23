import asyncio
import gzip
import json
import logging
import shutil

from state_of_soroban import checkpoints
from state_of_soroban.catalog import active_patterns
from state_of_soroban.config import ROOT
from state_of_soroban.extract.analyse import catalog_hash
from state_of_soroban.extract.shard_line import ShardLine
from state_of_soroban.runner import Context, stage
from state_of_soroban.stages.extract import store
from state_of_soroban.stages.gh import drop_artifacts, gh
from state_of_soroban.workflow import Stage

log = logging.getLogger("state_of_soroban")

JOB = "extract-run"
RUNS_DIR = ROOT / "out" / "extract-runs"


def read_lines(path):
    with gzip.open(path, "rt", encoding="utf-8") as source:
        for text in source:
            yield ShardLine.model_validate_json(text)


IMPORT_WORKERS = 8
DOWNLOADS = 6


async def import_file(context: Context, path) -> int:
    lines = await asyncio.to_thread(lambda: list(read_lines(path)))
    gate = asyncio.Semaphore(IMPORT_WORKERS)
    stored = 0

    async def one(line: ShardLine) -> None:
        nonlocal stored
        if line.analysis is None:
            await checkpoints.put(
                context.pool,
                "extract",
                line.repo,
                "gone" if line.gone else "failed",
                {},
                line.error or "",
            )
            context.errors += 1
            return
        try:
            async with gate, context.pool.acquire() as connection:
                await store(connection, line.repo, line.analysis, line.digest)
            stored += 1
        except Exception as error:
            context.errors += 1
            await checkpoints.put(
                context.pool, "extract", line.repo, "failed", {}, str(error)[:200]
            )
            log.warning("could not store %s: %s", line.repo, str(error)[:160])

    await asyncio.gather(*(one(line) for line in lines))
    return stored


async def download(run_id: str, target, names: list[str]) -> None:
    gate = asyncio.Semaphore(DOWNLOADS)

    async def fetch(name: str) -> None:
        if any((target / name).glob("*.jsonl.gz")):
            return
        async with gate:
            shutil.rmtree(target / name, ignore_errors=True)
            await gh("run", "download", run_id, "-n", name, "-D", str(target / name))

    await asyncio.gather(*(fetch(name) for name in names))


@stage("git.harvest")
async def harvest(context: Context, _: Stage) -> None:
    if shutil.which("gh") is None:
        return
    try:
        listing = json.loads(
            await gh(
                "run",
                "list",
                "--workflow",
                "extract.yml",
                "--status",
                "completed",
                "--limit",
                "100",
                "--json",
                "databaseId,conclusion",
            )
        )
    except RuntimeError as error:
        log.warning("could not list extract runs: %s", error)
        return
    for run in listing:
        run_id = str(run["databaseId"])
        saved = await checkpoints.get(context.pool, JOB, run_id)
        if saved and saved.done:
            continue
        target = RUNS_DIR / run_id
        try:
            names = json.loads(
                await gh(
                    "api",
                    f"repos/devodii/state-of-soroban/actions/runs/{run_id}/artifacts?per_page=100",
                    "--jq",
                    "[.artifacts[] | select(.expired | not) | .name]",
                )
            )
            await download(run_id, target, names)
        except RuntimeError as error:
            await checkpoints.put(context.pool, JOB, run_id, "failed", {}, str(error))
            context.errors += 1
            continue
        if not names:
            await checkpoints.put(context.pool, JOB, run_id, "done", {"repos": 0})
            continue
        stored = 0
        for file in sorted(target.rglob("*.jsonl.gz")):
            key = f"{run_id}/{file.parent.name}"
            saved_file = await checkpoints.get(context.pool, "extract-file", key)
            if saved_file and saved_file.done:
                continue
            count = await import_file(context, file)
            stored += count
            await checkpoints.put(
                context.pool, "extract-file", key, "done", {"repos": count}
            )
            log.info("imported %s, %s repos", key, count)
        await checkpoints.put(context.pool, JOB, run_id, "done", {"repos": stored})
        shutil.rmtree(target, ignore_errors=True)
        await drop_artifacts(run_id)
        context.items += stored
        log.info("extract run %s imported, %s repos", run_id, stored)


async def current_digest(context: Context) -> str:
    return catalog_hash(await active_patterns(context.pool, context.catalog))
