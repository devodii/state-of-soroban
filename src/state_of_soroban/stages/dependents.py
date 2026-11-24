import asyncio
import html
import logging
import re

import asyncpg
import httpx
from pydantic import BaseModel

from state_of_soroban import checkpoints
from state_of_soroban.resilience import resilient
from state_of_soroban.runner import Context, stage
from state_of_soroban.sql_loader import load_sql
from state_of_soroban.workflow import Stage

log = logging.getLogger("state_of_soroban")

JOB = "dependents"
AGENT = "Mozilla/5.0 (compatible; state-of-soroban research indexer)"
PAUSE = 1.5
MENU = re.compile(
    r'select-menu-item-text">\s*([^<]+?)\s*</span>.*?'
    r'dependents\?package_id=([A-Za-z0-9=]+)"',
    re.S,
)
MENU_LINK = re.compile(r'dependents\?package_id=([A-Za-z0-9=]+)"[^>]*>(.*?)</a>', re.S)
NAME = re.compile(r'select-menu-item-text">\s*([^<]+?)\s*</span>')
ROW = re.compile(r'data-hovercard-type="repository"[^>]*href="/([^/"]+/[^/"]+)"')
NEXT = re.compile(r'href="([^"]*dependents_after=[^"]+)"[^>]*>Next</a>')


class Package(BaseModel):
    name: str
    id: str


def packages_of(page: str) -> list[Package]:
    found = []
    for link in MENU_LINK.finditer(page):
        label = NAME.search(link.group(2))
        if label:
            found.append(Package(name=label.group(1).strip(), id=link.group(1)))
    return found


async def fetch(context: Context, url: str) -> str:
    wait = 30.0

    async def call() -> httpx.Response:
        return await context.http.get(
            url, headers={"User-Agent": AGENT}, timeout=40, follow_redirects=True
        )

    while True:
        response = await resilient(context.http, call)
        if response.status_code in (429, 502, 503):
            delay = float(response.headers.get("retry-after", wait))
            log.info("dependents paused %ss (%s)", int(delay), response.status_code)
            await asyncio.sleep(delay)
            wait = min(wait * 2, 900)
            continue
        response.raise_for_status()
        return response.text


async def crawl(context: Context, root: str, package: Package) -> int:
    key = f"{root}|{package.name}"
    saved = await checkpoints.get(context.pool, JOB, key)
    if saved and saved.done:
        return 0
    url = (
        saved.cursor.get("next")
        if saved and saved.cursor.get("next")
        else f"https://github.com/{root}/network/dependents?package_id={package.id}"
    )
    via = f"dependents:{package.name}"
    stored = 0
    pages = saved.cursor.get("pages", 0) if saved else 0
    while url:
        page = await fetch(context, url)
        names = sorted(set(ROW.findall(page)))
        if names:
            rows = [
                (n, f"https://github.com/{n}", n.split("/")[0], [via], [])
                for n in names
            ]
            for attempt in range(5):
                try:
                    await context.pool.executemany(load_sql("upsert_discovered"), rows)
                    break
                except asyncpg.DeadlockDetectedError:
                    await asyncio.sleep(1 + attempt)
            stored += len(names)
        pages += 1
        match = NEXT.search(page)
        url = html.unescape(match.group(1)) if match else None
        await checkpoints.put(
            context.pool,
            JOB,
            key,
            "running" if url else "done",
            {"next": url, "pages": pages},
        )
        context.items += len(names)
        if pages % 20 == 0:
            log.info("dependents %s: %s pages", key, pages)
        await asyncio.sleep(PAUSE)
    return stored


@stage("github.dependents")
async def dependents(context: Context, _: Stage) -> None:
    for source in context.workflow.discover.dependents:
        first = await fetch(
            context, f"https://github.com/{source.repo}/network/dependents"
        )
        found = packages_of(first)
        wanted = [p for p in found if not source.packages or p.name in source.packages]
        for package in wanted:
            added = await crawl(context, source.repo, package)
            log.info("dependents %s %s: %s repos", source.repo, package.name, added)
