import asyncio
import logging
from datetime import UTC, datetime
from pathlib import Path

import httpx

from state_of_soroban.config import ROOT
from state_of_soroban.runner import Context, stage
from state_of_soroban.scout.feed import Missing, ScoutFeed
from state_of_soroban.scout.taxonomy import normalise, read_taxonomy, refresh
from state_of_soroban.sql_loader import load_sql
from state_of_soroban.workflow import Stage

log = logging.getLogger("state_of_soroban")

USER_AGENT = "state-of-soroban-research"


async def trust(
    http: httpx.AsyncClient, base: str, gate: asyncio.Semaphore, repo: str
) -> dict | None | str:
    async with gate:
        for attempt in range(6):
            try:
                response = await http.get(
                    f"{base}/api/repos/trust",
                    params={"repo": repo},
                    headers={"User-Agent": USER_AGENT},
                    timeout=30,
                )
            except httpx.TransportError:
                await asyncio.sleep(2**attempt)
                continue
            if response.status_code == 404:
                return None
            if response.status_code == 429:
                await asyncio.sleep(8 * (attempt + 1))
                continue
            response.raise_for_status()
            return response.json()["report"]
    return "error"


@stage("scout.coverage")
async def coverage(context: Context, _: Stage) -> None:
    config = context.workflow.scout
    cache = ROOT / config.taxonomy_cache
    await refresh(config.taxonomy_remote, cache)
    taxonomy = read_taxonomy(cache)
    rows = await context.pool.fetch(
        load_sql("scout_active"),
        config.window_days,
        config.min_commits,
        config.min_authors,
    )
    names = {row["repo"] for row in rows}
    kept = [
        row
        for row in rows
        if row["family"] == row["repo"] or row["family"] not in names
    ]
    gate = asyncio.Semaphore(config.concurrency)
    reports = await asyncio.gather(
        *(trust(context.http, config.base_url, gate, row["repo"]) for row in kept)
    )
    missing: list[Missing] = []
    errors = 0
    for row, report in zip(kept, reports, strict=True):
        activity = {
            **{
                key: row[key]
                for key in (
                    "repo",
                    "url",
                    "family",
                    "family_members",
                    "commits",
                    "authors",
                    "active_weeks",
                    "top_author_share",
                    "stars",
                    "last_commit",
                )
            }
        }
        if report == "error":
            errors += 1
        elif report is None:
            spread = (
                row["active_weeks"] >= config.min_active_weeks
                and row["top_author_share"] <= config.max_top_author_share
            )
            address = normalise(row["url"])
            missing.append(
                Missing(
                    **activity,
                    spread=spread,
                    in_taxonomy=address in taxonomy.listed,
                    removed_from_taxonomy=address in taxonomy.removed,
                )
            )
    checked = len(kept)
    feed = ScoutFeed(
        generated_at=datetime.now(UTC),
        scout=config.base_url,
        window_days=config.window_days,
        min_commits=config.min_commits,
        min_authors=config.min_authors,
        min_active_weeks=config.min_active_weeks,
        max_top_author_share=config.max_top_author_share,
        repos_checked=checked,
        in_scout=checked - len(missing) - errors,
        not_in_scout=len(missing),
        errors=errors,
        taxonomy_repos=len(taxonomy.listed),
        missing=missing,
    )
    path = Path(ROOT / config.feed_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(feed.model_dump_json(indent=2) + "\n")
    proposed = sorted(
        item.url
        for item in missing
        if item.spread and not item.in_taxonomy and not item.removed_from_taxonomy
    )
    migration = Path(ROOT / config.migration_path)
    migration.write_text("".join(f"repadd Stellar {url}\n" for url in proposed))
    context.items += checked
    log.info(
        "scout: %s repos checked, %s missing, %s errors, %s to propose",
        checked,
        len(missing),
        errors,
        len(proposed),
    )
