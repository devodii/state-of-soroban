import logging
import shutil
from datetime import UTC, datetime

from state_of_soroban import checkpoints
from state_of_soroban.config import ROOT
from state_of_soroban.drive import pending
from state_of_soroban.runner import Context, stage
from state_of_soroban.workflow import Stage

log = logging.getLogger("state_of_soroban")

REPORT = ROOT / "out" / "report.md"
COUNTS = {
    "repos found": "SELECT count(*) FROM repos",
    "repos with details": "SELECT count(*) FROM repos WHERE pushed_at IS NOT NULL",
    "repos scanned": "SELECT count(*) FROM repos WHERE scanned_at IS NOT NULL",
    "in scope but too large to scan": "SELECT count(*) FROM repos WHERE pushed_at >= '2026-01-01' AND languages ? 'Rust' AND size_kb > 750000",
    "gave up on after retries": "SELECT count(*) FROM checkpoints WHERE job IN ('extract', 'history') AND (status = 'gone' OR (status = 'failed' AND attempts >= 3))",
    "confirmed soroban repos": "SELECT count(*) FROM repos WHERE is_soroban",
    "functions parsed": "SELECT count(*) FROM functions",
    "pattern matches": "SELECT count(*) FROM pattern_matches",
    "commits": "SELECT count(*) FROM commits",
    "fix commits": "SELECT count(*) FROM commits WHERE is_fix",
    "issues": "SELECT count(*) FROM issues WHERE kind = 'issue'",
    "pull requests": "SELECT count(*) FROM issues WHERE kind = 'pull'",
    "releases": "SELECT count(*) FROM releases",
    "contract ids in code": "SELECT count(DISTINCT contract_id) FROM repo_contract_refs",
    "contracts confirmed on chain": "SELECT count(*) FROM deployed_contracts",
    "wasm modules read": "SELECT count(*) FROM wasm_modules",
    "ledger days imported": "SELECT count(*) FROM chain_days WHERE status = 'done'",
    "contract-day activity rows": "SELECT count(*) FROM contract_activity",
    "contract call edges": "SELECT count(*) FROM contract_edges",
    "proposals": "SELECT count(*) FROM proposals",
    "mined patterns": "SELECT count(*) FROM patterns WHERE origin = 'mined'",
    "open candidates": "SELECT count(*) FROM catalog_candidates WHERE status = 'open'",
}


def arrow(now: int, before: int | None) -> str:
    if before is None or now == before:
        return ""
    return f" ({'+' if now > before else ''}{now - before:,})"


@stage("report.write")
async def write_report(context: Context, _: Stage) -> None:
    pool = context.pool
    now = {name: await pool.fetchval(sql) for name, sql in COUNTS.items()}
    saved = await checkpoints.get(pool, "report", "last")
    before = (saved.cursor if saved else {}).get("counts", {})
    stamp = datetime.now(UTC)
    earlier = (saved.cursor if saved else {}).get("at")
    hours = (
        (stamp - datetime.fromisoformat(earlier)).total_seconds() / 3600
        if earlier
        else 0
    )
    lines = [
        "# State of Soroban report",
        "",
        f"Written {datetime.now(UTC):%Y-%m-%d %H:%M} UTC. Changes are since the previous report.",
        "",
    ]
    lines += ["## Numbers", ""]
    lines += [
        f"- **{name}:** {value:,}{arrow(value, before.get(name))}"
        for name, value in now.items()
    ]
    work = await pending(context)
    estimates = []
    for label, key, counter in (
        ("extraction", "clone", "repos scanned"),
        ("issues and pull requests", "history", "confirmed soroban repos"),
        ("repo details", "metadata", "repos with details"),
    ):
        left = work.get(key, 0)
        rate = (
            (now[counter] - before.get(counter, now[counter])) / hours
            if hours > 0.05
            else 0
        )
        if key == "history":
            rate = (
                (
                    (
                        await pool.fetchval(
                            "SELECT count(*) FROM checkpoints WHERE job = 'history' AND status = 'done'"
                        )
                    )
                    - before.get("history done", 0)
                )
                / hours
                if hours > 0.05
                else 0
            )
        if left and rate > 0:
            estimates.append(
                f"- {label}: {left:,} left at about {rate:,.0f} per hour, roughly {left / rate:.1f} hours"
            )
        elif left:
            estimates.append(f"- {label}: {left:,} left (rate not measured yet)")
        else:
            estimates.append(f"- {label}: nothing left")
    lines += ["", "## Time remaining (from the measured rate)", "", *estimates]
    days = await pool.fetchrow(
        "SELECT min(day) AS first, max(day) AS last FROM chain_days WHERE status = 'done'"
    )
    if days["first"]:
        lines += ["", f"On-chain history imported: {days['first']} to {days['last']}."]
    lines += ["", "## Stage health (latest run of each)", ""]
    for row in await pool.fetch(
        "SELECT DISTINCT ON (stage) stage, status, items, errors, "
        "round(extract(epoch FROM coalesce(finished_at, now()) - started_at)) AS seconds "
        "FROM stage_runs ORDER BY stage, started_at DESC"
    ):
        lines.append(
            f"- {row['stage']}: {row['status']}, {row['items']:,} items, {row['errors']} errors, {int(row['seconds'])}s"
        )
    failed = await pool.fetchval(
        "SELECT count(*) FROM checkpoints WHERE status = 'failed'"
    )
    lines += [
        "",
        f"Units of work currently marked failed (they retry on their own): **{failed}**",
        "",
    ]
    lines += [
        "## Top proposals",
        "",
        "| score | proposal | origin | status | owners | repos |",
        "|---|---|---|---|---|---|",
    ]
    for row in await pool.fetch(
        "SELECT name, origin, status, score, evidence->'metrics'->>'owners' AS owners, "
        "evidence->'metrics'->>'repos' AS repos FROM proposals ORDER BY score DESC LIMIT 15"
    ):
        lines.append(
            f"| {float(row['score']):.1f} | {row['name'][:80]} | {row['origin']} | {row['status']} | {row['owners']} | {row['repos']} |"
        )
    lines += ["", "## What the miner found", ""]
    for row in await pool.fetch(
        "SELECT kind, count(*) AS n FROM catalog_candidates GROUP BY kind ORDER BY n DESC"
    ):
        lines.append(f"- {row['kind']}: {row['n']:,}")
    lines += ["", "Strongest new search topics it proposed:", ""]
    for row in await pool.fetch(
        "SELECT signature, repos, status FROM catalog_candidates WHERE kind = 'query' ORDER BY repos DESC LIMIT 6"
    ):
        lines.append(
            f"- `topic:{row['signature']}` ({row['repos']} confirmed repos, {row['status']})"
        )
    lines += ["", "Hand-written macros people keep rewriting:", ""]
    for row in await pool.fetch(
        "SELECT title, repos FROM catalog_candidates WHERE kind = 'macro' ORDER BY score DESC LIMIT 6"
    ):
        lines.append(f"- {row['title']} ({row['repos']} repos)")
    free = shutil.disk_usage(ROOT).free / 1e9
    size = await pool.fetchval(
        "SELECT pg_size_pretty(pg_database_size(current_database()))"
    )
    lines += [
        "",
        "## Infrastructure",
        "",
        f"- database size: {size}",
        f"- free disk on this machine: {free:.0f} GB",
        "",
    ]
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines))
    history_done = await pool.fetchval(
        "SELECT count(*) FROM checkpoints WHERE job = 'history' AND status = 'done'"
    )
    await checkpoints.put(
        pool,
        "report",
        "last",
        "done",
        {"counts": {**now, "history done": history_done}, "at": stamp.isoformat()},
    )
    context.items = len(now)
    log.info("report written to %s", REPORT)
