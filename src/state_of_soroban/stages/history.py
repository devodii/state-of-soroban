import asyncio
import json
import logging
import re
from datetime import UTC, datetime

from state_of_soroban import checkpoints
from state_of_soroban.extract.matcher import compiled
from state_of_soroban.resilience import NETWORK_ERRORS, until_online
from state_of_soroban.runner import Context, stage
from state_of_soroban.sql_loader import load_sql
from state_of_soroban.workflow import Stage

log = logging.getLogger("state_of_soroban")

JOB = "history"
CONCURRENCY = 8
MAX_PAGES = 12
BODY_LIMIT = 20000
BUG_LABEL = re.compile(r"(?i)bug|defect|security|vulnerab|regression|crash|panic")
ITEM = """
  number title body state createdAt closedAt url
  comments {{ totalCount }}
  reactions {{ totalCount }}
  author {{ login }}
  labels(first: 12) {{ nodes {{ name }} }}
"""
QUERY = """
query {{
  repository(owner: {owner}, name: {name}) {{
    issues(first: 100, {after_issues} orderBy: {{field: CREATED_AT, direction: DESC}},
           filterBy: {{since: "{since}"}}) {{
      pageInfo {{ hasNextPage endCursor }}
      nodes {{ {item} }}
    }}
    pullRequests(first: 100, {after_pulls} orderBy: {{field: CREATED_AT, direction: DESC}}) {{
      pageInfo {{ hasNextPage endCursor }}
      nodes {{ {item} mergedAt }}
    }}
    releases(first: 60, orderBy: {{field: CREATED_AT, direction: DESC}}) {{
      nodes {{ tagName name description isPrerelease publishedAt }}
    }}
  }}
}}
"""


def after(cursor: str | None) -> str:
    return f"after: {json.dumps(cursor)}," if cursor else ""


async def fetch_all(context: Context, name: str) -> tuple[list, list, list]:
    owner, repo = name.split("/")
    since = context.workflow.window.start.isoformat() + "T00:00:00Z"
    cutoff = datetime.combine(
        context.workflow.window.start, datetime.min.time(), tzinfo=UTC
    )
    issues: list[dict] = []
    pulls: list[dict] = []
    releases: list[dict] = []
    cursors: dict[str, str | None] = {"issues": None, "pulls": None}
    more = {"issues": True, "pulls": True}
    for _ in range(MAX_PAGES):
        data = await context.github.graphql(
            QUERY.format(
                owner=json.dumps(owner),
                name=json.dumps(repo),
                since=since,
                after_issues=after(cursors["issues"]),
                after_pulls=after(cursors["pulls"]),
                item=ITEM.format(),
            )
        )
        node = data.get("repository")
        if node is None:
            return [], [], []
        if more["issues"]:
            issues += node["issues"]["nodes"]
            info = node["issues"]["pageInfo"]
            more["issues"] = info["hasNextPage"]
            cursors["issues"] = info["endCursor"]
        if more["pulls"]:
            fresh = [
                p
                for p in node["pullRequests"]["nodes"]
                if datetime.fromisoformat(p["createdAt"]) >= cutoff
            ]
            pulls += fresh
            info = node["pullRequests"]["pageInfo"]
            more["pulls"] = info["hasNextPage"] and len(fresh) == len(
                node["pullRequests"]["nodes"]
            )
            cursors["pulls"] = info["endCursor"]
        releases = node["releases"]["nodes"]
        if not (more["issues"] or more["pulls"]):
            break
    return issues, pulls, releases


def issue_row(context: Context, repo: str, item: dict, kind: str) -> tuple:
    title = (item["title"] or "").replace("\x00", "")
    body = (item["body"] or "").replace("\x00", "")[:BODY_LIMIT]
    labels = [label["name"] for label in item["labels"]["nodes"]]
    text = f"{title}\n{body}"
    fix = compiled(context.workflow.history.fix_message)
    classes = [
        b.id for b in context.catalog.bug_classes if compiled(b.keywords).search(text)
    ]
    created = datetime.fromisoformat(item["createdAt"])
    closed = datetime.fromisoformat(item["closedAt"]) if item["closedAt"] else None
    merged = datetime.fromisoformat(item["mergedAt"]) if item.get("mergedAt") else None
    return (
        repo,
        item["number"],
        kind,
        title,
        body,
        item["state"].lower(),
        (item["author"] or {}).get("login"),
        labels,
        item["comments"]["totalCount"],
        created,
        closed,
        merged,
        any(BUG_LABEL.search(label) for label in labels) or bool(fix.search(title)),
        classes,
        item["url"],
        (item.get("reactions") or {}).get("totalCount", 0),
    )


@stage("github.history")
async def history(context: Context, _: Stage) -> None:
    async with context.pool.acquire() as connection:
        targets = [
            row["full_name"]
            for row in await connection.fetch(
                load_sql("history_targets"), context.force
            )
        ]
    if context.limit:
        targets = targets[: context.limit]
    gate = asyncio.Semaphore(CONCURRENCY)
    cutoff = datetime.combine(
        context.workflow.window.start, datetime.min.time(), tzinfo=UTC
    )

    async def one(name: str) -> None:
        async with gate:
            while True:
                try:
                    issues, pulls, releases = await fetch_all(context, name)
                    break
                except NETWORK_ERRORS:
                    await until_online(context.http)
                except Exception as error:
                    context.errors += 1
                    await checkpoints.put(
                        context.pool, JOB, name, "failed", {}, str(error)[:300]
                    )
                    log.warning("history failed for %s: %s", name, str(error)[:120])
                    return
            rows = [
                issue_row(context, name, i, "issue")
                for i in issues
                if datetime.fromisoformat(i["createdAt"]) >= cutoff
            ] + [issue_row(context, name, p, "pull") for p in pulls]
            async with context.pool.acquire() as connection, connection.transaction():
                await connection.executemany(load_sql("ins_issue"), rows)
                await connection.executemany(
                    load_sql("ins_release"),
                    [
                        (
                            name,
                            r["tagName"],
                            r["name"],
                            (r["description"] or "").replace("\x00", "")[:BODY_LIMIT],
                            r["isPrerelease"],
                            datetime.fromisoformat(r["publishedAt"])
                            if r["publishedAt"]
                            else None,
                        )
                        for r in releases
                        if r["publishedAt"]
                        and datetime.fromisoformat(r["publishedAt"]) >= cutoff
                    ],
                )
            await checkpoints.put(
                context.pool, JOB, name, "done", {"issues": len(rows)}
            )
            context.items += 1
            if context.items % 50 == 0:
                log.info("history for %s/%s repos", context.items, len(targets))

    await asyncio.gather(*(one(n) for n in targets))
