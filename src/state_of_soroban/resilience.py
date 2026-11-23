import asyncio
import logging
from collections.abc import Awaitable, Callable

import httpx

from state_of_soroban.github.client import GithubUnavailable

log = logging.getLogger("state_of_soroban")

NETWORK_ERRORS = (GithubUnavailable, httpx.TransportError, httpx.TimeoutException)
PROBE = "https://api.github.com/rate_limit"
MAX_PAUSE = 120


async def online(http: httpx.AsyncClient) -> bool:
    try:
        response = await http.get(PROBE, timeout=8)
    except NETWORK_ERRORS:
        return False
    return response.status_code < 500


async def until_online(http: httpx.AsyncClient) -> None:
    pause = 5
    while not await online(http):
        log.warning("offline, checking again in %ss", pause)
        await asyncio.sleep(pause)
        pause = min(pause * 2, MAX_PAUSE)


async def resilient[T](http: httpx.AsyncClient, call: Callable[[], Awaitable[T]]) -> T:
    while True:
        try:
            return await call()
        except NETWORK_ERRORS as error:
            log.warning(
                "network trouble (%s: %s), waiting to resume",
                type(error).__name__,
                str(error)[:120],
            )
            await until_online(http)
