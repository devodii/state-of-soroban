from pathlib import Path

import asyncpg
from pydantic import BaseModel

from state_of_soroban.config import ROOT
from state_of_soroban.sql_loader import load_sql
from state_of_soroban.workflow import Workflow

MIN_OVERLAP = 30


class Signal(BaseModel):
    name: str
    passed: bool
    value: str
    target: str


class ReadinessReport(BaseModel):
    signals: list[Signal]

    @property
    def ready(self) -> bool:
        return all(s.passed for s in self.signals)

    def markdown(self) -> str:
        rows = [
            f"| {'pass' if s.passed else 'wait'} | {s.name} | {s.value} | {s.target} |"
            for s in self.signals
        ]
        head = (
            "# Indexing readiness\n\n| | signal | now | needed |\n|---|---|---|---|\n"
        )
        verdict = (
            "\nReady: run the friction layer."
            if self.ready
            else "\nNot ready yet: keep the autopilot running."
        )
        return head + "\n".join(rows) + "\n" + verdict + "\n"


def estimate(first: int, second: int, both: int, confirmed: int) -> float | None:
    if both < MIN_OVERLAP:
        return None
    return confirmed / (first * second / both)


async def check(pool: asyncpg.Pool, workflow: Workflow) -> ReadinessReport:
    config = workflow.readiness
    channels = dict(
        await pool.fetchrow(load_sql("readiness_channels"), config.quiet_hours)
    )
    work = dict(
        await pool.fetchrow(
            load_sql("pending_work"),
            workflow.window.start,
            workflow.clone.require_language or "",
            workflow.clone.max_repo_kb,
            workflow.clone.include_forks,
        )
    )
    signals = [
        Signal(
            name="relevant repos fully read",
            passed=not any(work.values()),
            value=", ".join(f"{k} {v}" for k, v in work.items()),
            target="all zero",
        ),
        Signal(
            name=f"new Soroban repos in the last {config.quiet_hours}h",
            passed=channels["running_hours"] >= config.quiet_hours
            and channels["recent"] <= config.max_new_soroban_in_quiet,
            value=f"{channels['recent']} new, running {channels['running_hours']:.0f}h",
            target=f"at most {config.max_new_soroban_in_quiet} after {config.quiet_hours}h of running",
        ),
    ]
    pairs = [
        (
            "code vs search",
            channels["code"],
            channels["search"],
            channels["code_search"],
        ),
        ("code vs graph", channels["code"], channels["graph"], channels["code_graph"]),
        (
            "search vs graph",
            channels["search"],
            channels["graph"],
            channels["search_graph"],
        ),
    ]
    recalls = [
        r
        for _, a, b, both in pairs
        if (r := estimate(a, b, both, channels["confirmed"])) is not None
    ]
    worst = min(recalls) if recalls else None
    signals.append(
        Signal(
            name="estimated recall (independent channels, lowest pair)",
            passed=worst is not None and worst >= config.min_recall,
            value="not enough overlap yet" if worst is None else f"{100 * worst:.1f}%",
            target=f"at least {100 * config.min_recall:.0f}%",
        )
    )
    if config.known_file:
        path = (
            ROOT / config.known_file
            if not Path(config.known_file).is_absolute()
            else Path(config.known_file)
        )
        if path.is_file():
            known = [
                line.strip() for line in path.read_text().splitlines() if line.strip()
            ]
            found = await pool.fetchval(
                "SELECT count(*) FROM repos WHERE is_soroban AND full_name = ANY($1)",
                known,
            )
            share = found / max(len(known), 1)
            signals.append(
                Signal(
                    name="known Soroban repos rediscovered",
                    passed=share >= config.min_known_rediscovered,
                    value=f"{found} of {len(known)} ({100 * share:.1f}%)",
                    target=f"at least {100 * config.min_known_rediscovered:.0f}%",
                )
            )
    return ReadinessReport(signals=signals)
