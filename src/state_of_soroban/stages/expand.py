import asyncio
import logging

from state_of_soroban import checkpoints
from state_of_soroban.resilience import NETWORK_ERRORS, until_online
from state_of_soroban.runner import Context, stage
from state_of_soroban.sql_loader import load_sql
from state_of_soroban.workflow import Stage

log = logging.getLogger("state_of_soroban")

PAGE_SIZE = 100


def user_row(user: dict) -> tuple:
    return (
        user["login"],
        user["avatar_url"],
        user.get("html_url"),
        user.get("type"),
    )


async def read_pages(context: Context, path: str, pages: int) -> list[dict]:
    items: list[dict] = []
    for page in range(1, pages + 1):
        batch = await context.github.json(
            path, {"per_page": PAGE_SIZE, "page": page, "sort": "newest"}
        )
        if not batch:
            break
        items += batch
        if len(batch) < PAGE_SIZE:
            break
    return items


async def expand_forks(context: Context, parent: str) -> int:
    items = await read_pages(
        context, f"/repos/{parent}/forks", context.workflow.expansion.fork_pages
    )
    rows = [
        (
            item["full_name"],
            f"https://github.com/{item['full_name']}",
            item["owner"]["login"],
            [f"forks:{parent}"],
            [],
            parent,
        )
        for item in items
    ]
    users = {item["owner"]["login"]: user_row(item["owner"]) for item in items}
    async with context.pool.acquire() as connection:
        await connection.executemany(load_sql("upsert_fork"), rows)
        await connection.executemany(load_sql("upsert_user"), list(users.values()))
    return len(rows)


async def expand_contributors(context: Context, repo: str) -> int:
    items = await read_pages(
        context,
        f"/repos/{repo}/contributors",
        context.workflow.expansion.contributor_pages,
    )
    people = [i for i in items if i.get("login")]
    async with context.pool.acquire() as connection:
        await connection.executemany(
            load_sql("upsert_user"), [user_row(p) for p in people]
        )
        await connection.executemany(
            load_sql("upsert_repo_contributor"),
            [(repo, p["login"], p["contributions"]) for p in people],
        )
    return len(people)


CHANNELS = {"forks": expand_forks, "contributors": expand_contributors}


@stage("github.expand")
async def expand(context: Context, _: Stage) -> None:
    gate = asyncio.Semaphore(context.workflow.expansion.concurrency)

    async def one(job: str, repo: str) -> None:
        async with gate:
            while True:
                try:
                    count = await CHANNELS[job](context, repo)
                    break
                except NETWORK_ERRORS:
                    await until_online(context.http)
                except Exception as error:
                    context.errors += 1
                    await checkpoints.put(
                        context.pool, job, repo, "failed", {}, str(error)[:200]
                    )
                    return
            await checkpoints.put(context.pool, job, repo, "done", {"count": count})
            context.items += 1

    for job in CHANNELS:
        rows = await context.pool.fetch(load_sql("expand_targets"), context.force, job)
        repos = [row["full_name"] for row in rows]
        if context.limit:
            repos = repos[: context.limit]
        log.info("expand %s: %s repos", job, len(repos))
        await asyncio.gather(*(one(job, repo) for repo in repos))
