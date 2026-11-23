import asyncio
import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

from state_of_soroban.github.client import GithubClient, GithubUnavailable, Search

log = logging.getLogger("state_of_soroban")

PAGE_SIZE = 100
RESULT_CAP = 1000
SIZE_CEILING = 400_000
OUTAGE_ROUNDS = 5
OUTAGE_PAUSE = 60

Count = Callable[[int, int], Awaitable[int]]


async def split_range(
    lo: int, hi: int, count: Count, cap: int = RESULT_CAP
) -> list[tuple[int, int]]:
    if lo >= hi or await count(lo, hi) <= cap:
        return [(lo, hi)]
    middle = (lo + hi) // 2
    left, right = await asyncio.gather(
        split_range(lo, middle, count, cap), split_range(middle + 1, hi, count, cap)
    )
    return left + right


def _stamp(seconds: int) -> str:
    return datetime.fromtimestamp(seconds, UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


async def _total(github: GithubClient, path: str, query: str, kind: Search) -> int:
    data = await github.json(path, {"q": query, "per_page": 1}, search=kind)
    return data["total_count"] if data else 0


async def repository_slices(
    github: GithubClient, query: str, since: datetime, until: datetime
) -> list[str]:
    async def count(lo: int, hi: int) -> int:
        pushed = f"pushed:{_stamp(lo)}..{_stamp(hi)}"
        return await _total(
            github, "/search/repositories", f"{query} {pushed}", "repositories"
        )

    ranges = await split_range(int(since.timestamp()), int(until.timestamp()), count)
    return [f"{query} pushed:{_stamp(lo)}..{_stamp(hi)}" for lo, hi in ranges]


async def code_slices(github: GithubClient, query: str) -> list[str]:
    if await _total(github, "/search/code", query, "code") <= RESULT_CAP:
        return [query]

    async def count(lo: int, hi: int) -> int:
        return await _total(github, "/search/code", f"{query} size:{lo}..{hi}", "code")

    return [
        f"{query} size:{lo}..{hi}"
        for lo, hi in await split_range(0, SIZE_CEILING, count)
    ]


async def pages(
    github: GithubClient, path: str, query: str, kind: Search, start: int = 1
) -> AsyncIterator[tuple[int, list[dict[str, Any]]]]:
    for page in range(start, RESULT_CAP // PAGE_SIZE + 1):
        data = await github.json(
            path, {"q": query, "per_page": PAGE_SIZE, "page": page}, search=kind
        )
        items = data["items"] if data else []
        yield page, items
        if len(items) < PAGE_SIZE:
            return


async def hits(
    github: GithubClient, path: str, query: str, kind: Search
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for page in range(1, RESULT_CAP // PAGE_SIZE + 1):
        data = await github.json(
            path, {"q": query, "per_page": PAGE_SIZE, "page": page}, search=kind
        )
        batch = data["items"] if data else []
        items.extend(batch)
        if len(batch) < PAGE_SIZE:
            break
    return items


async def patient(query: str, run: Callable[[str], Awaitable[None]]) -> None:
    for _ in range(OUTAGE_ROUNDS):
        try:
            await run(query)
            return
        except GithubUnavailable:
            log.warning("github unreachable, retrying in %ss: %s", OUTAGE_PAUSE, query)
            await asyncio.sleep(OUTAGE_PAUSE)
    log.error("gave up after %s rounds: %s", OUTAGE_ROUNDS, query)
