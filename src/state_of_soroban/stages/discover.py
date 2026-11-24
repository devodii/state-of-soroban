import asyncio
import logging
import time
from datetime import UTC, datetime

from pydantic import BaseModel, Field

from state_of_soroban import checkpoints
from state_of_soroban.github.search import (
    PAGE_SIZE,
    RESULT_CAP,
    code_slices,
    pages,
    repository_slices,
)
from state_of_soroban.linking.repo_ref import normalize_repo
from state_of_soroban.resilience import NETWORK_ERRORS, resilient, until_online
from state_of_soroban.runner import Context, stage
from state_of_soroban.sources.crates_io import (
    Throttle,
    crate_repository,
    reverse_dependency_names,
)
from state_of_soroban.sql_loader import load_sql
from state_of_soroban.workflow import Stage

log = logging.getLogger("state_of_soroban")

JOB = "discover"


class Found(BaseModel):
    full_name: str
    via: set[str] = Field(default_factory=set)
    crates: set[str] = Field(default_factory=set)


class Harvest(BaseModel):
    repos: dict[str, Found] = Field(default_factory=dict)
    dirty: set[str] = Field(default_factory=set)

    def note(self, full_name: str, via: str, crate: str | None = None) -> None:
        key = full_name.lower()
        found = self.repos.setdefault(key, Found(full_name=full_name))
        found.via.add(via)
        if crate:
            found.crates.add(crate)
        self.dirty.add(key)


async def flush(context: Context, harvest: Harvest) -> None:
    excluded = {r.lower() for r in context.workflow.discover.exclude_repos}
    keys = [k for k in sorted(harvest.dirty) if k not in excluded]
    harvest.dirty.clear()
    rows = [
        (
            harvest.repos[k].full_name,
            f"https://github.com/{harvest.repos[k].full_name}",
            harvest.repos[k].full_name.split("/")[0],
            sorted(harvest.repos[k].via),
            sorted(harvest.repos[k].crates),
        )
        for k in keys
    ]
    if rows:
        async with context.pool.acquire() as connection:
            await connection.executemany(load_sql("upsert_discovered"), rows)
    async with context.pool.acquire() as connection:
        context.items = await connection.fetchval("SELECT count(*) FROM repos")


async def plan_slices(
    context: Context, kind: str, query: str, expanded: str
) -> list[str]:
    key = f"plan|{kind}|{query}"
    saved = await checkpoints.get(context.pool, JOB, key)
    if saved and saved.done:
        return list(saved.cursor["slices"])
    window = context.workflow.window
    if kind == "search":
        since = datetime.combine(window.start, datetime.min.time(), tzinfo=UTC)
        until = datetime.combine(window.end, datetime.max.time(), tzinfo=UTC)
        slices = await resilient(
            context.http,
            lambda: repository_slices(context.github, expanded, since, until),
        )
    else:
        slices = await resilient(
            context.http, lambda: code_slices(context.github, expanded)
        )
    await checkpoints.put(context.pool, JOB, key, "done", {"slices": slices})
    return slices


async def read_slice(
    context: Context, harvest: Harvest, kind: str, query: str, sliced: str
) -> None:
    key = f"page|{kind}|{sliced}"
    saved = await checkpoints.get(context.pool, JOB, key)
    if saved and saved.done:
        return
    start = saved.cursor.get("page", 0) + 1 if saved else 1
    path = "/search/repositories" if kind == "search" else "/search/code"
    search_kind = "repositories" if kind == "search" else "code"
    page = start - 1
    excluded = {o.lower() for o in context.workflow.discover.exclude_owners}
    while True:
        try:
            async for current, items in pages(
                context.github, path, sliced, search_kind, page + 1
            ):
                for item in items:
                    repository = item if kind == "search" else item["repository"]
                    if repository["owner"]["login"].lower() not in excluded:
                        harvest.note(repository["full_name"], f"{kind}:{query}")
                await flush(context, harvest)
                page = current
                capped = current >= RESULT_CAP // PAGE_SIZE and len(items) == PAGE_SIZE
                await checkpoints.put(
                    context.pool,
                    JOB,
                    key,
                    "done" if len(items) < PAGE_SIZE or capped else "running",
                    {"page": page, "saturated": capped},
                )
            return
        except NETWORK_ERRORS as error:
            log.warning(
                "%s on %s page %s, resuming", type(error).__name__, kind, page + 1
            )
            await until_online(context.http)
        except Exception as error:
            await checkpoints.put(
                context.pool, JOB, key, "failed", {"page": page}, str(error)[:300]
            )
            raise


async def run_query(context: Context, harvest: Harvest, kind: str, query: str) -> None:
    started = time.monotonic()
    expanded = context.workflow.expand(query)
    slices = await plan_slices(context, kind, query, expanded)
    for sliced in slices:
        await read_slice(context, harvest, kind, query, sliced)
    via = f"{kind}:{query}"
    async with context.pool.acquire() as connection:
        counts = await connection.fetchrow(load_sql("query_stat_counts"), via)
        await connection.execute(
            load_sql("upsert_query_stat"),
            kind,
            query,
            counts["hits"],
            counts["exclusive"],
            time.monotonic() - started,
        )
    log.info(
        "%s done: %s repos (%s only here)", via, counts["hits"], counts["exclusive"]
    )


async def crates_io(context: Context, harvest: Harvest) -> None:
    config = context.workflow.discover.crates_io
    throttle = Throttle()
    names: dict[str, str] = {}
    for crate in config.crates:
        key = f"crate|{crate}"
        saved = await checkpoints.get(context.pool, JOB, key)
        if saved and saved.done:
            names.update({n: crate for n in saved.cursor["names"]})
            continue
        found = [crate]
        if config.reverse_dependencies:
            found += await resilient(
                context.http,
                lambda crate=crate: reverse_dependency_names(
                    context.http, throttle, crate
                ),
            )
        await checkpoints.put(context.pool, JOB, key, "done", {"names": found})
        names.update({n: crate for n in found})
    for name, via in names.items():
        key = f"crate_repo|{name}"
        saved = await checkpoints.get(context.pool, JOB, key)
        if saved and saved.done:
            continue
        found = await resilient(
            context.http,
            lambda name=name: crate_repository(context.http, throttle, name),
        )
        if found.repo and normalize_repo(found.repo):
            harvest.note(found.repo, f"crates.io:{via}", name)
            await flush(context, harvest)
        await checkpoints.put(context.pool, JOB, key, "done", {"repo": found.repo})
    log.info("crates.io: %s crates covered", len(names))


@stage("github.discover")
async def discover(context: Context, _: Stage) -> None:
    harvest = Harvest()
    config = context.workflow.discover
    jobs = [
        *(run_query(context, harvest, "search", q) for q in config.repository_queries),
        *(run_query(context, harvest, "code", q) for q in config.code_queries),
        crates_io(context, harvest),
    ]
    await asyncio.gather(*jobs)
    await flush(context, harvest)
    log.info("discovered %s repos", context.items)
