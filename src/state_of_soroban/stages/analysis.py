import json
import logging
import shutil
from datetime import UTC, datetime

from state_of_soroban import checkpoints
from state_of_soroban.analysis.export import export_units
from state_of_soroban.analysis.records import (
    ClusterInfo,
    Member,
    RepoUsecase,
    RunMetrics,
    UsecaseInfo,
    read_jsonl,
)
from state_of_soroban.config import ROOT
from state_of_soroban.runner import Context, stage
from state_of_soroban.sql_loader import load_sql
from state_of_soroban.stages.evidence import build as build_evidence
from state_of_soroban.stages.gh import gh
from state_of_soroban.workflow import Stage

log = logging.getLogger("state_of_soroban")

JOB = "analysis-run"
RUNS_DIR = ROOT / "out" / "analysis-runs"
WORKFLOW = "analyse.yml"


GIVE_UP = 3
BAD = {"failure", "cancelled", "timed_out", "startup_failure"}


async def recent_runs() -> list[dict]:
    return json.loads(
        await gh(
            "run",
            "list",
            "--workflow",
            WORKFLOW,
            "--limit",
            "10",
            "--json",
            "databaseId,status,conclusion,createdAt",
        )
    )


def age_hours(created: str) -> float:
    moment = datetime.fromisoformat(created.replace("Z", "+00:00"))
    return (datetime.now(UTC) - moment).total_seconds() / 3600


async def healthy_to_run(context: Context, runs: list[dict]) -> bool:
    config = context.workflow.analysis
    for run in runs:
        if run["status"] != "completed":
            if age_hours(run["createdAt"]) > config.max_run_hours:
                await gh("run", "cancel", str(run["databaseId"]))
                log.warning(
                    "cancelled analysis run %s stuck for too long", run["databaseId"]
                )
            return False
    done = [run for run in runs if run["status"] == "completed"]
    if done and done[0]["conclusion"] == "success":
        saved = await checkpoints.get(context.pool, JOB, str(done[0]["databaseId"]))
        if not (saved and (saved.done or saved.attempts >= GIVE_UP)):
            return False
    streak = 0
    for run in done:
        if run["conclusion"] not in BAD:
            break
        streak += 1
    if (
        streak >= config.max_failures
        and age_hours(done[0]["createdAt"]) < config.retry_hours
    ):
        log.warning(
            "analysis failed %s times in a row, waiting before retrying", streak
        )
        return False
    return True


@stage("analysis.dispatch")
async def dispatch(context: Context, node: Stage) -> None:
    if shutil.which("gh") is None:
        return
    try:
        runs = await recent_runs()
        if not await healthy_to_run(context, runs):
            return
        total = await context.pool.fetchval(load_sql("analysis_source_count"))
        last = await context.pool.fetchval(
            "SELECT source_count FROM analysis_runs ORDER BY created_at DESC LIMIT 1"
        )
        failed_last = bool(runs) and runs[0]["conclusion"] in BAD
        grown = last is None or total >= last * (
            1 + context.workflow.analysis.rerun_growth
        )
        if not (grown or failed_last):
            return
        await build_evidence(context, node)
        await export_units()
        shards = context.workflow.analysis.shards
        await gh("workflow", "run", WORKFLOW, "-f", f"shards={shards}")
        context.detail["source_count"] = total
        log.info("dispatched an analysis run over %s shards", shards)
    except RuntimeError as error:
        context.errors += 1
        log.warning("could not dispatch an analysis run: %s", error)


async def import_usecases(connection, run_id: str) -> None:
    target = RUNS_DIR / f"{run_id}-usecases"
    shutil.rmtree(target, ignore_errors=True)
    try:
        await gh("run", "download", run_id, "-n", "usecases-result", "-D", str(target))
    except RuntimeError:
        return
    await connection.executemany(
        load_sql("usecase_put"),
        [
            (run_id, u.usecase, u.size, u.terms)
            for u in read_jsonl(target / "usecases.jsonl.gz", UsecaseInfo)
        ],
    )
    await connection.executemany(
        load_sql("repo_usecase_put"),
        [
            (run_id, r.repo, r.usecase, r.sim)
            for r in read_jsonl(target / "repo_usecases.jsonl.gz", RepoUsecase)
        ],
    )
    shutil.rmtree(target, ignore_errors=True)


@stage("analysis.harvest")
async def harvest(context: Context, _: Stage) -> None:
    if shutil.which("gh") is None:
        return
    listing = json.loads(
        await gh(
            "run",
            "list",
            "--workflow",
            WORKFLOW,
            "--status",
            "completed",
            "--limit",
            "20",
            "--json",
            "databaseId,conclusion",
        )
    )
    for run in listing:
        run_id = str(run["databaseId"])
        saved = await checkpoints.get(context.pool, JOB, run_id)
        if run["conclusion"] != "success":
            continue
        if saved and (saved.done or saved.attempts >= GIVE_UP):
            continue
        target = RUNS_DIR / run_id
        shutil.rmtree(target, ignore_errors=True)
        try:
            await gh(
                "run", "download", run_id, "-n", "analysis-result", "-D", str(target)
            )
            metrics = RunMetrics.model_validate_json(
                (target / "metrics.json").read_text()
            )
        except (RuntimeError, OSError, ValueError) as error:
            context.errors += 1
            await checkpoints.put(
                context.pool, JOB, run_id, "failed", {}, str(error)[:200]
            )
            log.warning("could not read analysis run %s: %s", run_id, error)
            continue
        total = await context.pool.fetchval(load_sql("analysis_source_count"))
        async with context.pool.acquire() as connection, connection.transaction():
            await connection.execute(
                load_sql("analysis_run_put"), run_id, total, metrics.model_dump()
            )
            await connection.executemany(
                load_sql("friction_put"),
                [
                    (run_id, c.cluster, c.terms, c.size, c.cohesion, c.parts, c.medoids)
                    for c in read_jsonl(target / "clusters.jsonl.gz", ClusterInfo)
                ],
            )
            batch = []
            for member in read_jsonl(target / "members.jsonl.gz", Member):
                kind, repo, ref = member.id.split("|", 2)
                batch.append((run_id, kind, repo, ref, member.cluster, member.sim))
                if len(batch) >= 20000:
                    await connection.executemany(load_sql("friction_member_put"), batch)
                    batch = []
            await connection.executemany(load_sql("friction_member_put"), batch)
            await import_usecases(connection, run_id)
            await connection.execute("ANALYZE friction_members")
            await connection.execute(load_sql("friction_stats"), run_id)
            await connection.execute(load_sql("analysis_prune"), run_id)
        await checkpoints.put(context.pool, JOB, run_id, "done", metrics.model_dump())
        shutil.rmtree(target, ignore_errors=True)
        context.items += 1
        log.info("analysis run %s imported: %s clusters", run_id, metrics.clusters)
