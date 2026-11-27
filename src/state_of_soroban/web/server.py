import json
from pathlib import Path

from aiohttp import web
from pydantic import BaseModel

from state_of_soroban.config import ROOT
from state_of_soroban.database import open_pool
from state_of_soroban.sql_loader import load_sql
from state_of_soroban.workflow import load_workflow

STATIC = Path(__file__).parent / "static"


class Page(BaseModel):
    q: str = ""
    kind: str = "all"
    sort: str = "stars"
    repo: str = ""
    fixes: bool = False
    bugs: bool = False
    type: str = ""
    page: int = 0

    @classmethod
    def read(cls, request: web.Request) -> "Page":
        return cls.model_validate(dict(request.query))


def dump(data) -> str:
    return json.dumps(data, default=str)


def rows(records) -> list[dict]:
    return [dict(record) for record in records]


async def stats(request: web.Request) -> web.Response:
    row = await request.app["pool"].fetchrow(load_sql("web_stats"))
    return web.json_response(dict(row))


async def repos(request: web.Request) -> web.Response:
    config = request.app["config"]
    page = Page.read(request)
    sort = page.sort if page.sort in config.repo_sorts else config.repo_sorts[0]
    found = rows(
        await request.app["pool"].fetch(
            load_sql("web_repos"),
            page.q,
            page.kind,
            config.page_size,
            page.page * config.page_size,
            sort,
        )
    )
    total = found[0]["total"] if found else 0
    return web.json_response(
        {"rows": found, "total": total, "page_size": config.page_size},
        dumps=dump,
    )


async def repo(request: web.Request) -> web.Response:
    name = request.match_info["name"]
    pool = request.app["pool"]
    row = await pool.fetchrow(load_sql("web_repo"), name)
    if row is None:
        raise web.HTTPNotFound
    people = await pool.fetch(load_sql("web_repo_contributors"), name)
    return web.json_response(
        {"repo": dict(row), "contributors": rows(people)},
        dumps=dump,
    )


async def commits(request: web.Request) -> web.Response:
    config = request.app["config"]
    page = Page.read(request)
    found = rows(
        await request.app["pool"].fetch(
            load_sql("web_commits"),
            page.repo,
            page.q,
            page.fixes,
            config.page_size + 1,
            page.page * config.page_size,
        )
    )
    return web.json_response(
        {"rows": found[: config.page_size], "more": len(found) > config.page_size},
        dumps=dump,
    )


async def issues(request: web.Request) -> web.Response:
    config = request.app["config"]
    page = Page.read(request)
    found = rows(
        await request.app["pool"].fetch(
            load_sql("web_issues"),
            page.repo,
            page.q,
            page.bugs,
            page.type,
            config.page_size + 1,
            page.page * config.page_size,
        )
    )
    return web.json_response(
        {"rows": found[: config.page_size], "more": len(found) > config.page_size},
        dumps=dump,
    )


async def users(request: web.Request) -> web.Response:
    config = request.app["config"]
    page = Page.read(request)
    found = rows(
        await request.app["pool"].fetch(
            load_sql("web_users"),
            page.q,
            config.page_size + 1,
            page.page * config.page_size,
        )
    )
    return web.json_response(
        {"rows": found[: config.page_size], "more": len(found) > config.page_size},
        dumps=dump,
    )


async def frictions(request: web.Request) -> web.Response:
    config = request.app["config"]
    query = request.query
    found = rows(
        await request.app["pool"].fetch(
            load_sql("web_frictions"),
            int(query.get("min_families", 5)),
            query.get("q", ""),
            float(query.get("contract_share", 0)),
            query.get("sort", "families"),
            config.page_size,
            int(query.get("page", 0)) * config.page_size,
        )
    )
    total = found[0]["total"] if found else 0
    return web.json_response(
        {"rows": found, "total": total, "page_size": config.page_size}, dumps=dump
    )


async def friction(request: web.Request) -> web.Response:
    cluster = int(request.match_info["cluster"])
    kind = request.query.get("kind", "")
    page = int(request.query.get("page", 0))
    pool = request.app["pool"]
    size = request.app["config"].page_size
    evidence = rows(
        await pool.fetch(
            load_sql("web_friction_evidence"), cluster, kind, size + 1, page * size
        )
    )
    repos = rows(await pool.fetch(load_sql("web_friction_repos"), cluster))
    usecases = rows(
        await pool.fetch(
            load_sql("web_friction_usecases"),
            cluster,
            request.app["workflow"].analysis.min_usecase_families,
        )
    )
    return web.json_response(
        {
            "evidence": evidence[:size],
            "more": len(evidence) > size,
            "repos": repos,
            "usecases": usecases,
        },
        dumps=dump,
    )


async def index(_: web.Request) -> web.FileResponse:
    return web.FileResponse(STATIC / "index.html")


async def days(request: web.Request) -> web.FileResponse:
    return web.FileResponse(ROOT / request.app["config"].days_dir / "index.html")


async def days_redirect(_: web.Request) -> web.Response:
    raise web.HTTPFound("/21days/")


async def start(app: web.Application) -> None:
    app["pool"] = await open_pool(8)


async def stop(app: web.Application) -> None:
    await app["pool"].close()


def serve(port: int | None = None) -> None:
    workflow = load_workflow()
    config = workflow.web
    app = web.Application()
    app["config"] = config
    app["workflow"] = workflow
    app.on_startup.append(start)
    app.on_cleanup.append(stop)
    app.add_routes(
        [
            web.get("/", index),
            web.get("/api/stats", stats),
            web.get("/api/repos", repos),
            web.get("/api/repo/{name:.+}", repo),
            web.get("/api/commits", commits),
            web.get("/api/issues", issues),
            web.get("/api/users", users),
            web.get("/api/frictions", frictions),
            web.get("/api/friction/{cluster}", friction),
            web.get("/21days", days_redirect),
            web.get("/21days/", days),
            web.static("/21days", ROOT / config.days_dir),
            web.static("/static", STATIC),
        ]
    )
    web.run_app(app, host="127.0.0.1", port=port or config.port)
