import asyncio
import logging
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import AsyncExitStack, asynccontextmanager

import asyncpg
import httpx
from pydantic import BaseModel, ConfigDict, Field

from state_of_soroban.catalog import Catalog, load_catalog
from state_of_soroban.config import Settings, get_settings
from state_of_soroban.database import open_pool
from state_of_soroban.github.client import GithubClient
from state_of_soroban.sql_loader import load_sql
from state_of_soroban.workflow import Stage, Workflow, load_workflow

log = logging.getLogger("state_of_soroban")


class Context(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    workflow: Workflow
    catalog: Catalog
    pool: asyncpg.Pool
    http: httpx.AsyncClient
    github: GithubClient
    force: bool = False
    limit: int | None = None
    items: int = 0
    errors: int = 0
    detail: dict[str, object] = Field(default_factory=dict)


StageFunction = Callable[[Context, Stage], Awaitable[None]]
REGISTRY: dict[str, StageFunction] = {}


def stage(name: str) -> Callable[[StageFunction], StageFunction]:
    def register(function: StageFunction) -> StageFunction:
        REGISTRY[name] = function
        return function

    return register


def order(stages: list[Stage]) -> list[Stage]:
    by_id = {s.id: s for s in stages}
    ordered: list[Stage] = []
    seen: set[str] = set()

    def visit(item: Stage, trail: tuple[str, ...]) -> None:
        if item.id in trail:
            raise ValueError(f"stage cycle through {item.id}")
        if item.id in seen:
            return
        for need in item.needs:
            visit(by_id[need], (*trail, item.id))
        seen.add(item.id)
        ordered.append(item)

    for item in stages:
        visit(item, ())
    return ordered


def select(
    stages: list[Stage], only: list[str], skip: list[str], start: str | None
) -> list[Stage]:
    ordered = order(stages)
    ids = [s.id for s in ordered]
    for name in [*only, *skip, *([start] if start else [])]:
        if name not in ids:
            raise ValueError(f"unknown stage {name}, choose from {', '.join(ids)}")
    if start:
        ordered = ordered[ids.index(start) :]
    if only:
        ordered = [s for s in ordered if s.id in only]
    return [s for s in ordered if s.id not in skip]


async def watch_tokens(github: GithubClient) -> None:
    while True:
        await asyncio.sleep(30)
        try:
            fresh = Settings().github_tokens
        except Exception:
            continue
        added = github.add_tokens(fresh)
        if added:
            log.info("picked up %s new github token(s) from .env", added)


@asynccontextmanager
async def session(
    force: bool = False, limit: int | None = None, pool_size: int = 10
) -> AsyncIterator[Context]:
    from state_of_soroban import stages as _stages  # noqa: F401

    workflow = load_workflow()
    async with AsyncExitStack() as stack:
        pool = await open_pool(pool_size)
        stack.push_async_callback(pool.close)
        http = await stack.enter_async_context(
            httpx.AsyncClient(
                timeout=60,
                limits=httpx.Limits(max_connections=200, max_keepalive_connections=50),
            )
        )
        github = GithubClient(http, get_settings().github_tokens)
        watcher = asyncio.create_task(watch_tokens(github))
        try:
            yield Context(
                workflow=workflow,
                catalog=load_catalog(workflow),
                pool=pool,
                http=http,
                github=github,
                force=force,
                limit=limit,
            )
        finally:
            watcher.cancel()


async def run_stage(parent: Context, item: Stage) -> Context:
    function = REGISTRY.get(item.uses)
    if function is None:
        raise ValueError(f"{item.id} uses {item.uses}, which is not built yet")
    context = parent.model_copy(update={"items": 0, "errors": 0, "detail": {}})
    started = time.monotonic()
    log.info("stage %s (%s)", item.id, item.uses)
    run_id = await context.pool.fetchval(load_sql("stage_run_start"), item.id)
    status = "failed"
    try:
        await function(context, item)
        status = "done"
    finally:
        await context.pool.execute(
            load_sql("stage_run_finish"),
            run_id,
            status,
            context.items,
            context.errors,
            context.detail,
        )
        log.info(
            "stage %s %s in %.1fs, %s items, %s errors",
            item.id,
            status,
            time.monotonic() - started,
            context.items,
            context.errors,
        )
    return context


async def run_workflow(
    only: list[str],
    skip: list[str],
    start: str | None,
    force: bool = False,
    limit: int | None = None,
) -> None:
    async with session(force, limit) as context:
        for item in select(context.workflow.stages, only, skip, start):
            await run_stage(context, item)
