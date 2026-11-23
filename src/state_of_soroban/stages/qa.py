import asyncio
import html
import logging
from datetime import UTC, datetime

import httpx

from state_of_soroban import checkpoints
from state_of_soroban.resilience import NETWORK_ERRORS, until_online
from state_of_soroban.runner import Context, stage
from state_of_soroban.sql_loader import load_sql
from state_of_soroban.workflow import Stage

log = logging.getLogger("state_of_soroban")

API = "https://api.stackexchange.com/2.3/questions"
SITES = {"stellar": "stellar.stackexchange.com"}
JOB = "qa"


async def fetch_page(http: httpx.AsyncClient, site: str, page: int) -> dict:
    response = await http.get(
        API,
        params={
            "site": site,
            "page": page,
            "pagesize": 100,
            "order": "asc",
            "sort": "creation",
            "filter": "withbody",
        },
        headers={"Accept-Encoding": "gzip"},
        timeout=60,
    )
    response.raise_for_status()
    return response.json()


@stage("qa.stackexchange")
async def stackexchange(context: Context, _: Stage) -> None:
    for site in SITES:
        saved = await checkpoints.get(context.pool, JOB, site)
        page = saved.cursor.get("page", 0) + 1 if saved and not saved.done else 1
        if saved and saved.done and not context.force:
            page = saved.cursor.get("page", 0) + 1
        while True:
            try:
                data = await fetch_page(context.http, site, page)
            except NETWORK_ERRORS:
                await until_online(context.http)
                continue
            items = data.get("items", [])
            rows = [
                (
                    site,
                    q["question_id"],
                    html.unescape(q["title"]),
                    html.unescape(q.get("body", ""))[:20000].replace("\x00", ""),
                    q.get("tags", []),
                    q["score"],
                    q["view_count"],
                    q["answer_count"],
                    bool(q.get("is_answered")),
                    datetime.fromtimestamp(q["creation_date"], UTC),
                    q["link"],
                )
                for q in items
            ]
            if rows:
                await context.pool.executemany(load_sql("upsert_qa_post"), rows)
            context.items += len(rows)
            more = data.get("has_more", False)
            await checkpoints.put(
                context.pool, JOB, site, "running" if more else "done", {"page": page}
            )
            if not more:
                break
            page += 1
            await asyncio.sleep(max(data.get("backoff", 0), 1))
        log.info("%s: %s questions stored", site, context.items)
