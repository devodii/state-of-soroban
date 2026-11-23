import asyncio
import json
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import asyncpg
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from state_of_soroban import api_app
from state_of_soroban.config import ROOT
from state_of_soroban.database import open_pool
from state_of_soroban.sql_loader import load_sql

UI_DIR = Path(__file__).with_name("ui")
WEB_DIST = ROOT / "web" / "dist"
MIN_OVERLAP = 30


class CommentIn(BaseModel):
    target_kind: str = Field(
        pattern="^(repo|proposal|pattern|contract|node|need|tool)$"
    )
    target_id: str = Field(min_length=1, max_length=300)
    author: str = Field(default="anonymous", max_length=80)
    body: str = Field(min_length=1, max_length=4000)


def records(rows: list[asyncpg.Record]) -> list[dict[str, Any]]:
    return [dict(row) for row in rows]


def recall(found: dict[str, Any]) -> dict[str, Any]:
    text, content, both = found["by_text"], found["by_content"], found["by_both"]
    reliable = both >= MIN_OVERLAP
    estimate = ((text + 1) * (content + 1) / (both + 1) - 1) if reliable else None
    return {
        **found,
        "estimated_total": round(estimate) if estimate else None,
        "estimated_missing": round(estimate - found["confirmed"]) if estimate else None,
        "note": "Lincoln-Petersen estimate from text search vs content search overlap"
        if reliable
        else f"not enough overlap yet ({both} of the {MIN_OVERLAP} needed), content search is still running",
    }


OVERVIEW_QUERIES = [
    "counts",
    "stages",
    "patterns",
    "proposals",
    "candidates",
    "queries",
    "networks",
    "needs",
    "top_contracts",
    "top_edges",
    "network_days",
]
REFRESH_SECONDS = 900


async def one(pool: asyncpg.Pool, name: str, *args: Any) -> Any:
    async def fetch() -> list[dict[str, Any]]:
        async with pool.acquire() as connection:
            return records(await connection.fetch(load_sql(f"overview_{name}"), *args))

    if name in HEAVY and SNAPSHOTS is not None:
        return await SNAPSHOTS.get(
            f"part:{name}",
            fetch,
            HEAVY[name],
            fallback=[{}] if name == "counts" else [],
        )
    return await fetch()


async def overview(pool: asyncpg.Pool, limit: int) -> dict[str, Any]:
    names = OVERVIEW_QUERIES
    results = await asyncio.gather(
        *[one(pool, name) for name in names],
        one(pool, "repos", limit),
        one(pool, "recall"),
    )
    data: dict[str, Any] = {
        name: records(rows) if rows and not isinstance(rows[0], dict) else rows
        for name, rows in zip(names, results, strict=False)
    }
    data["counts"] = data["counts"][0]
    data["repos"] = records(results[-2])
    data["recall"] = recall(dict(results[-1][0]))
    return data


CACHE_DIR = ROOT / "out" / "cache"
HEAVY = {"top_edges": 14400, "top_contracts": 14400, "patterns": 7200, "counts": 1800}


class Snapshots:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self.pool = pool
        self.values: dict[str, tuple[float, Any]] = {}
        self.busy: dict[str, asyncio.Task[Any]] = {}
        CACHE_DIR.mkdir(parents=True, exist_ok=True)

    def file(self, key: str) -> Path:
        return CACHE_DIR / (key.replace(":", "_").replace("/", "_") + ".json")

    async def refresh(self, key: str, make: Any) -> Any:
        try:
            value = json.loads(json.dumps(await make(), default=str))
            self.values[key] = (time.monotonic(), value)
            self.file(key).write_text(json.dumps(value))
            return value
        finally:
            self.busy.pop(key, None)

    def start(self, key: str, make: Any) -> asyncio.Task[Any]:
        task = self.busy.get(key)
        if task is None:
            task = self.busy[key] = asyncio.create_task(self.refresh(key, make))
        return task

    async def get(
        self, key: str, make: Any, ttl: int = REFRESH_SECONDS, fallback: Any = None
    ) -> Any:
        cached = self.values.get(key)
        if cached is None:
            saved = self.file(key)
            if saved.exists():
                value = json.loads(saved.read_text())
                self.values[key] = (0.0, value)
                self.start(key, make)
                return value
            task = self.start(key, make)
            if fallback is not None:
                return fallback
            return await task
        if time.monotonic() - cached[0] > ttl:
            self.start(key, make)
        return cached[1]


SNAPSHOTS: Snapshots | None = None


async def graph(pool: asyncpg.Pool) -> dict[str, Any]:
    async with pool.acquire() as a, pool.acquire() as b:
        nodes, edges = await asyncio.gather(
            a.fetch(load_sql("graph_nodes")), b.fetch(load_sql("graph_edges"))
        )
    return {"nodes": records(nodes), "edges": records(edges)}


def create_app() -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.pool = await open_pool()
        app.state.snapshots = Snapshots(app.state.pool)
        global SNAPSHOTS
        SNAPSHOTS = app.state.snapshots
        app.state.v2 = api_app.Cache()
        asyncio.create_task(api_app.warm(app))
        asyncio.create_task(
            app.state.snapshots.get(
                "overview:500", lambda: overview(app.state.pool, 500)
            )
        )
        asyncio.create_task(
            app.state.snapshots.get("graph", lambda: graph(app.state.pool))
        )
        yield
        await app.state.pool.close()

    app = FastAPI(title="state-of-soroban", lifespan=lifespan)
    app.add_middleware(GZipMiddleware, minimum_size=1024)
    app.include_router(api_app.router)

    @app.get("/app", include_in_schema=False)
    @app.get("/app/{path:path}", include_in_schema=False)
    async def web_app(path: str = "") -> FileResponse:
        index = WEB_DIST / "index.html"
        if not index.exists():
            raise HTTPException(404, "web app is not built, run pnpm build in web")
        target = (WEB_DIST / path).resolve()
        if path and target.is_file() and WEB_DIST.resolve() in target.parents:
            return FileResponse(target)
        return FileResponse(index)

    @app.get("/")
    async def page() -> FileResponse:
        return FileResponse(UI_DIR / "index.html")

    @app.get("/api/overview")
    async def get_overview(request: Request, limit: int = 500) -> JSONResponse:
        size = min(limit, 5000)
        pool = request.app.state.pool
        data = await request.app.state.snapshots.get(
            f"overview:{size}", lambda: overview(pool, size)
        )
        return JSONResponse(data)

    @app.get("/report")
    async def report() -> FileResponse:
        path = ROOT / "out" / "report.md"
        if not path.exists():
            raise HTTPException(404, "no report yet")
        return FileResponse(path, media_type="text/plain; charset=utf-8")

    @app.get("/api/repo")
    async def get_repo(request: Request, name: str) -> JSONResponse:
        async with request.app.state.pool.acquire() as connection:
            row = await connection.fetchrow(load_sql("overview_repo"), name)
        if row is None:
            raise HTTPException(404, "unknown repo")
        return JSONResponse(json.loads(json.dumps(dict(row), default=str)))

    @app.get("/api/graph")
    async def get_graph(request: Request) -> JSONResponse:
        pool = request.app.state.pool
        data = await request.app.state.snapshots.get("graph", lambda: graph(pool))
        return JSONResponse(data)

    @app.get("/api/comments")
    async def list_comments(
        request: Request, target_kind: str, target_id: str
    ) -> JSONResponse:
        async with request.app.state.pool.acquire() as connection:
            rows = await connection.fetch(
                load_sql("comments_list"), target_kind, target_id
            )
        return JSONResponse(json.loads(json.dumps(records(rows), default=str)))

    @app.post("/api/comments")
    async def add_comment(request: Request, comment: CommentIn) -> JSONResponse:
        async with request.app.state.pool.acquire() as connection:
            row = await connection.fetchrow(
                load_sql("comments_add"),
                comment.target_kind,
                comment.target_id,
                comment.author,
                comment.body,
            )
        if row is None:
            raise HTTPException(500, "comment was not stored")
        return JSONResponse(json.loads(json.dumps(dict(row), default=str)))

    return app


app = create_app()
