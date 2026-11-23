import re
from functools import cache

from pydantic import BaseModel

from state_of_soroban.workflow import NetworkSignal

PROXIMITY = 40


class NetworkHit(BaseModel):
    network: str
    signal: str
    line: int
    evidence: str


@cache
def compiled(expression: str) -> re.Pattern[str]:
    return re.compile(expression)


def network_hits(
    text: str, signals: dict[str, list[NetworkSignal]]
) -> list[NetworkHit]:
    hits: list[NetworkHit] = []
    for number, line in enumerate(text.splitlines(), start=1):
        if len(line) > 2000:
            continue
        for network, items in signals.items():
            for item in items:
                if compiled(item.regex).search(line):
                    hits.append(
                        NetworkHit(
                            network=network,
                            signal=item.signal,
                            line=number,
                            evidence=line.strip()[:200],
                        )
                    )
    return hits


def network_of_ref(
    line: int, file_hits: list[NetworkHit], repo_networks: set[str]
) -> str:
    near = {h.network for h in file_hits if abs(h.line - line) <= PROXIMITY}
    for scope in (near, {h.network for h in file_hits}, repo_networks):
        scope = scope - {"futurenet"} if len(scope) > 1 else scope
        if len(scope) == 1:
            return next(iter(scope))
    return "unknown"
