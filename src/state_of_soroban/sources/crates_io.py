import asyncio
import time
from pathlib import Path

import httpx
from pydantic import BaseModel

from state_of_soroban.linking.repo_ref import normalize_repo

API = "https://crates.io/api/v1"
USER_AGENT = "state-of-soroban-indexer (community research)"
INTERVAL = 1.1
PAGE_SIZE = 100


class CrateRepository(BaseModel):
    crate: str
    repo: str | None
    updated_at: str | None = None
    downloads: int = 0


class Throttle:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._next = 0.0

    async def wait(self) -> None:
        async with self._lock:
            now = time.monotonic()
            delay = max(self._next - now, 0)
            self._next = max(now, self._next) + INTERVAL
        await asyncio.sleep(delay)


async def _get(
    http: httpx.AsyncClient, throttle: Throttle, path: str, params: dict | None = None
) -> dict | None:
    for attempt in range(5):
        await throttle.wait()
        response = await http.get(
            f"{API}{path}", params=params, headers={"User-Agent": USER_AGENT}
        )
        if response.status_code == 404:
            return None
        if response.status_code in (429, 500, 502, 503, 504):
            await asyncio.sleep(2**attempt)
            continue
        response.raise_for_status()
        return response.json()
    return None


async def reverse_dependency_names(
    http: httpx.AsyncClient, throttle: Throttle, crate: str
) -> list[str]:
    names: dict[str, None] = {}
    page = 1
    while True:
        data = await _get(
            http,
            throttle,
            f"/crates/{crate}/reverse_dependencies",
            {"page": page, "per_page": PAGE_SIZE},
        )
        if not data or not data["versions"]:
            break
        for version in data["versions"]:
            names[version["crate"]] = None
        if page * PAGE_SIZE >= data["meta"]["total"]:
            break
        page += 1
    return list(names)


async def crate_repository(
    http: httpx.AsyncClient, throttle: Throttle, name: str
) -> CrateRepository:
    data = await _get(http, throttle, f"/crates/{name}")
    if data is None:
        return CrateRepository(crate=name, repo=None)
    info = data["crate"]
    url = info.get("repository") or info.get("homepage") or ""
    return CrateRepository(
        crate=name,
        repo=normalize_repo(url) if "github" in url else None,
        updated_at=info.get("updated_at"),
        downloads=info.get("downloads", 0),
    )


async def crate_source(
    http: httpx.AsyncClient, throttle: Throttle, name: str, cache: Path
) -> tuple[str, bytes]:
    data = await _get(http, throttle, f"/crates/{name}")
    if data is None:
        raise ValueError(f"crate {name} not found")
    version = data["crate"]["max_stable_version"]
    saved = cache / f"{name}-{version}.crate"
    if saved.exists():
        return version, saved.read_bytes()
    for attempt in range(5):
        try:
            await throttle.wait()
            response = await http.get(
                f"{API}/crates/{name}/{version}/download",
                headers={"User-Agent": USER_AGENT},
            )
            response.raise_for_status()
            break
        except httpx.TransportError:
            if attempt == 4:
                raise
            await asyncio.sleep(2**attempt * 5)
    cache.mkdir(parents=True, exist_ok=True)
    saved.write_bytes(response.content)
    return version, response.content
