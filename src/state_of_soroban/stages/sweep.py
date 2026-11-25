import asyncio
import logging
from datetime import UTC, datetime

from state_of_soroban import checkpoints
from state_of_soroban.resilience import NETWORK_ERRORS, until_online
from state_of_soroban.runner import Context, stage
from state_of_soroban.sql_loader import load_sql
from state_of_soroban.workflow import Stage

log = logging.getLogger("state_of_soroban")

JOB = "sweep"
CONCURRENCY = 6
MAX_PAGES = 15


async def list_owner(context: Context, owner: str, cutoff: datetime) -> list[str]:
    found: list[str] = []
    for page in range(1, MAX_PAGES + 1):
        items = await context.github.json(
            f"/users/{owner}/repos",
            {
                "type": "owner",
                "sort": "pushed",
                "direction": "desc",
                "per_page": 100,
                "page": page,
            },
        )
        if not items:
            break
        fresh = [
            r
            for r in items
            if r.get("pushed_at")
            and datetime.fromisoformat(r["pushed_at"].replace("Z", "+00:00")) >= cutoff
            and not r.get("fork")
        ]
        found += [r["full_name"] for r in fresh]
        if len(fresh) < len(items) or len(items) < 100:
            break
    return found


@stage("github.sweep")
async def sweep(context: Context, _: Stage) -> None:
    cutoff = datetime.combine(
        context.workflow.window.start, datetime.min.time(), tzinfo=UTC
    )
    owners = [
        row["owner"]
        for row in await context.pool.fetch(
            load_sql("sweep_owners"),
            context.force,
            context.workflow.expansion.min_contributor_repos,
        )
    ]
    if context.limit:
        owners = owners[: context.limit]
    gate = asyncio.Semaphore(CONCURRENCY)
    added = 0

    async def one(owner: str) -> None:
        nonlocal added
        async with gate:
            while True:
                try:
                    names = await list_owner(context, owner, cutoff)
                    break
                except NETWORK_ERRORS:
                    await until_online(context.http)
                except Exception as error:
                    context.errors += 1
                    await checkpoints.put(
                        context.pool, JOB, owner, "failed", {}, str(error)[:200]
                    )
                    return
            rows = [
                (
                    name,
                    f"https://github.com/{name}",
                    name.split("/")[0],
                    [f"owner:{owner}"],
                    [],
                )
                for name in names
            ]
            if rows:
                await context.pool.executemany(load_sql("upsert_discovered"), rows)
            added += len(rows)
            await checkpoints.put(
                context.pool, JOB, owner, "done", {"repos": len(rows)}
            )
            context.items += 1
            if context.items % 100 == 0:
                log.info(
                    "swept %s/%s owners, %s repos listed",
                    context.items,
                    len(owners),
                    added,
                )

    await asyncio.gather(*(one(o) for o in owners))
    context.detail["repos_listed"] = added
