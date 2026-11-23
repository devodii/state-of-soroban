import asyncio
import logging
import shutil
import time
from datetime import UTC, datetime

from state_of_soroban.config import ROOT
from state_of_soroban.runner import REGISTRY, Context, run_stage, session
from state_of_soroban.sql_loader import load_sql

log = logging.getLogger("state_of_soroban")

FOLLOWED = {
    "metadata": "metadata",
    "ecosystem": "ecosystem",
    "history": "history",
}
PERIODIC = ["sweep", "chain", "dispatch", "harvest", "report"]
ANALYTICS = ["reanalyse", "mine", "score", "needs", "gaps", "graph"]
PERIOD = 600
ANALYTICS_PERIOD = 10800
RERUN_SECONDS = 3600
DEPENDENTS_SECONDS = 21600
IDLE_PAUSE = 45
MAX_BACKOFF = 600
POOL_SIZE = 40
MIN_FREE_BYTES = 3_000_000_000


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


async def keep_discovering(
    context: Context, discovered: asyncio.Event, quiet: asyncio.Event
) -> None:
    failures: dict[str, int] = {}
    while True:
        await safely(context, "discover", failures)
        if not failures.get("discover"):
            discovered.set()
            for _ in range(RERUN_SECONDS // 30):
                if quiet.is_set():
                    return
                await asyncio.sleep(30)
        else:
            await asyncio.sleep(1)


async def keep_dependents(context: Context, quiet: asyncio.Event) -> None:
    failures: dict[str, int] = {}
    while True:
        await safely(context, "dependents", failures)
        for _ in range(DEPENDENTS_SECONDS // 30):
            if quiet.is_set():
                return
            await asyncio.sleep(30)


async def follow(
    context: Context, stage_id: str, key: str, quiet: asyncio.Event
) -> None:
    failures: dict[str, int] = {}
    while True:
        work = (await pending(context)).get(key, 0)
        if (
            work
            and stage_id == "clone"
            and shutil.disk_usage(ROOT).free < MIN_FREE_BYTES
        ):
            log.warning("less than 3 GB free on disk, pausing extraction")
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
    failures: dict[str, int] = {}
    last = 0.0
    last_analytics = time.monotonic()
    while True:
        now = time.monotonic()
        if now - last > PERIOD or quiet.is_set():
            for stage_id in PERIODIC:
                await safely(context, stage_id, failures)
            last = time.monotonic()
        if time.monotonic() - last_analytics > ANALYTICS_PERIOD or quiet.is_set():
            for stage_id in ANALYTICS:
                await safely(context, stage_id, failures)
            last_analytics = time.monotonic()
            if quiet.is_set():
                return
        await asyncio.sleep(IDLE_PAUSE)


async def watch_quiet(
    context: Context, discovered: asyncio.Event, quiet: asyncio.Event
) -> None:
    calm = 0
    while True:
        work = await pending(context)
        if discovered.is_set() and not any(work.values()):
            calm += 1
        else:
            calm = 0
        if calm >= 2:
            log.info("nothing left to do, running the final pass")
            quiet.set()
            return
        log.info(
            "pending %s, discovery %s",
            work,
            "finished" if discovered.is_set() else "running",
        )
        await asyncio.sleep(120)


async def drive(force: bool = False) -> None:
    async with session(force, pool_size=POOL_SIZE) as context:
        quiet = asyncio.Event()
        discovered = asyncio.Event()
        tasks = [
            asyncio.create_task(keep_discovering(context, discovered, quiet)),
            asyncio.create_task(watch_quiet(context, discovered, quiet)),
            asyncio.create_task(periodic(context, quiet)),
            asyncio.create_task(keep_dependents(context, quiet)),
            *(
                asyncio.create_task(follow(context, stage_id, key, quiet))
                for stage_id, key in FOLLOWED.items()
            ),
        ]
        await asyncio.gather(*tasks)
