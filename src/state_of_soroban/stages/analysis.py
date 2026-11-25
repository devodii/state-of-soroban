import json
import logging
import shutil

from state_of_soroban import checkpoints
from state_of_soroban.analysis.export import export_units
from state_of_soroban.analysis.records import (
    ClusterInfo,
    Member,
    RunMetrics,
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


@stage("analysis.dispatch")
async def dispatch(context: Context, node: Stage) -> None:
    if shutil.which("gh") is None:
        return
    try:
        active = json.loads(
            await gh(
                "run",
                "list",
                "--workflow",
                WORKFLOW,
                "--limit",
                "5",
                "--json",
                "status",
            )
        )
        if any(run["status"] != "completed" for run in active):
            return
        total = await context.pool.fetchval(load_sql("analysis_source_count"))
        last = await context.pool.fetchval(
            "SELECT source_count FROM analysis_runs ORDER BY created_at DESC LIMIT 1"
        )
        growth = context.workflow.analysis.rerun_growth
        if last is not None and total < last * (1 + growth):
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
        if (saved and saved.done) or run["conclusion"] != "success":
            continue
        target = RUNS_DIR / run_id
        shutil.rmtree(target, ignore_errors=True)
        await gh("run", "download", run_id, "-n", "analysis-result", "-D", str(target))
        metrics = RunMetrics.model_validate_json((target / "metrics.json").read_text())
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
            await connection.execute(load_sql("friction_stats"), run_id)
            await connection.execute(load_sql("analysis_prune"), run_id)
        await checkpoints.put(context.pool, JOB, run_id, "done", metrics.model_dump())
        shutil.rmtree(target, ignore_errors=True)
        context.items += 1
        log.info("analysis run %s imported: %s clusters", run_id, metrics.clusters)
