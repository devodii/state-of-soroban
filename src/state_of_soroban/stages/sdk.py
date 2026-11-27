import logging
import re
from datetime import UTC, datetime
from pathlib import Path

from state_of_soroban.config import ROOT
from state_of_soroban.runner import Context, stage
from state_of_soroban.sdk.feed import Entry, Feed
from state_of_soroban.sdk.symbols import parse_crate
from state_of_soroban.sources.crates_io import Throttle, crate_source
from state_of_soroban.sql_loader import load_sql
from state_of_soroban.workflow import Stage

log = logging.getLogger("state_of_soroban")

PAGE_SPLIT = re.compile(r"\n(?=# [^\n]+\nSource: )")
PAGE_URL = re.compile(r"^# [^\n]+\nSource: (\S+)")


def read_pages(text: str) -> list[tuple[str, str]]:
    return [
        (match.group(1), page)
        for page in PAGE_SPLIT.split(text)[1:]
        if (match := PAGE_URL.match(page))
    ]


@stage("sdk.coverage")
async def coverage(context: Context, _: Stage) -> None:
    config = context.workflow.sdk
    pages = read_pages((await context.http.get(config.docs_text_url)).text)
    throttle = Throttle()
    scanned = await context.pool.fetchval(load_sql("sdk_repos_scanned"))
    for crate in config.crates:
        version, archive = await crate_source(
            context.http, throttle, crate, ROOT / config.cache_dir
        )
        symbols = {s.name: s for s in parse_crate(archive, set(config.owner_types))}
        usage = await context.pool.fetch(load_sql("sdk_usage"), list(symbols))
        entries: list[Entry] = []
        for row in usage:
            if row["repos"] < config.min_repos:
                continue
            if row["defining_repos"] > config.ambiguous_share * row["repos"]:
                continue
            name = row["name"]
            call = re.compile(rf"\b{re.escape(name)}\s*[(<]")
            urls = [url for url, text in pages if call.search(text)]
            deprecated = symbols[name].deprecated
            gaps = [
                *(["undocumented"] if not urls else []),
                *(["deprecated-still-used"] if deprecated else []),
                *(["docs-teach-deprecated"] if deprecated and urls else []),
            ]
            if not gaps:
                continue
            entries.append(
                Entry(
                    symbol=name,
                    repos=row["repos"],
                    repos_defining_same_name=row["defining_repos"],
                    docs_pages=len(urls),
                    docs_urls=urls[: config.max_docs_urls],
                    deprecated=deprecated,
                    gaps=gaps,
                    example_repos=list(row["example_repos"]),
                )
            )
        entries.sort(key=lambda entry: (-entry.repos, entry.symbol))
        feed = Feed(
            generated_at=datetime.now(UTC),
            crate=crate,
            version=version,
            docs_source=config.docs_text_url,
            docs_pages_read=len(pages),
            repos_scanned=scanned,
            entries=entries,
        )
        path = Path(ROOT / config.feed_path.format(crate=crate))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(feed.model_dump_json(indent=2) + "\n")
        context.items += len(entries)
        log.info(
            "sdk: %s %s has %s gaps, written to %s", crate, version, len(entries), path
        )
