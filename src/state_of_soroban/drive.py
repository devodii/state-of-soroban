import asyncio
import logging
import shutil
from datetime import UTC, datetime

from state_of_soroban.config import ROOT
from state_of_soroban.readiness import check
from state_of_soroban.runner import REGISTRY, Context, run_stage, session
from state_of_soroban.sql_loader import load_sql

log = logging.getLogger("state_of_soroban")

IDLE_PAUSE = 45
MAX_BACKOFF = 600
READY_FILE = ROOT / "out" / "READY.md"


async def pending(context: Context) -> dict[str, int]:
    cutoff = datetime.combine(
        context.workflow.window.start, datetime.min.time(), tzinfo=UTC
    )
    row = await context.pool.fetchrow(
        load_sql("pending_work"),
        cutoff,
        context.workflow.clone.require_language or "",
        context.workflow.clone.max_repo_kb,
    )
    return dict(row)


async def safely(context: Context, stage_id: str, failures: dict[str, int]) -> None:
    item = next((s for s in context.workflow.stages if s.id == stage_id), None)
    if item is None or item.uses not in REGISTRY:
        return
    try:
        await run_stage(context, item)
        failures[stage_id] = 0
    except Exception:
        failures[stage_id] = failures.get(stage_id, 0) + 1
        pause = min(30 * failures[stage_id], MAX_BACKOFF)
        log.exception("%s crashed, resuming in %ss", stage_id, pause)
        await asyncio.sleep(pause)


async def repeat(
    context: Context, stage_id: str, seconds: int, quiet: asyncio.Event
) -> None:
    failures: dict[str, int] = {}
    while not quiet.is_set():
        await safely(context, stage_id, failures)
        for _ in range(max(seconds // 30, 1)):
            if quiet.is_set():
                return
            await asyncio.sleep(30)


async def follow(
    context: Context, stage_id: str, key: str, quiet: asyncio.Event
) -> None:
    failures: dict[str, int] = {}
    floor = context.workflow.autopilot.min_free_gb * 1_000_000_000
    while True:
        work = (await pending(context)).get(key, 0)
        if work and shutil.disk_usage(ROOT).free < floor:
            log.warning("low disk space, pausing %s", stage_id)
            await asyncio.sleep(300)
            continue
        if work:
            await safely(context, stage_id, failures)
            await asyncio.sleep(5)
            continue
        if quiet.is_set():
            return
        await asyncio.sleep(IDLE_PAUSE)


async def periodic(context: Context, quiet: asyncio.Event) -> None:
    config = context.workflow.autopilot
    failures: dict[str, int] = {}
    while True:
        for stage_id in config.periodic:
            await safely(context, stage_id, failures)
        if quiet.is_set():
            return
        await asyncio.sleep(config.periodic_seconds)


async def write_stats(context: Context, quiet: asyncio.Event) -> None:
    path = ROOT / "out" / "stats.log"
    path.parent.mkdir(parents=True, exist_ok=True)
    while True:
        row = dict(await context.pool.fetchrow(load_sql("pipeline_stats")))
        work = await pending(context)
        line = " ".join(
            f"{k}={v}"
            for k, v in {**row, **{f"pending_{k}": v for k, v in work.items()}}.items()
        )
        with path.open("a") as handle:
            handle.write(f"{datetime.now(UTC):%Y-%m-%d %H:%M:%S} {line}\n")
        if quiet.is_set():
            return
        await asyncio.sleep(context.workflow.autopilot.stats_seconds)


async def watch_ready(context: Context, quiet: asyncio.Event) -> None:
    while True:
        work = await pending(context)
        report = await check(context.pool, context.workflow)
        log.info("pending %s, ready %s", work, report.ready)
        if report.ready and not any(work.values()):
            READY_FILE.parent.mkdir(parents=True, exist_ok=True)
            READY_FILE.write_text(report.markdown())
            log.info("indexing is complete, see %s", READY_FILE)
            quiet.set()
            return
        await asyncio.sleep(300)


async def drive(force: bool = False) -> None:
    async with session(force, pool_size=40) as context:
        config = context.workflow.autopilot
        quiet = asyncio.Event()
        tasks = [
            asyncio.create_task(
                repeat(context, "discover", config.discovery_seconds, quiet)
            ),
            asyncio.create_task(
                repeat(context, "dependents", config.dependents_seconds, quiet)
            ),
            asyncio.create_task(periodic(context, quiet)),
            asyncio.create_task(watch_ready(context, quiet)),
            asyncio.create_task(write_stats(context, quiet)),
            *(
                asyncio.create_task(follow(context, stage_id, key, quiet))
                for stage_id, key in config.followed.items()
            ),
        ]
        await asyncio.gather(*tasks)
        log.info("autopilot finished")
