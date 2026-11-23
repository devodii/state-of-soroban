import json
import logging
import math
import shutil

from state_of_soroban import checkpoints
from state_of_soroban.extract.plan import run_plan
from state_of_soroban.runner import Context, stage
from state_of_soroban.stages.gh import gh
from state_of_soroban.workflow import Stage

log = logging.getLogger("state_of_soroban")

MIN_QUEUE = 200
REPOS_PER_SHARD = 250
MAX_SHARDS = 100


@stage("git.dispatch")
async def dispatch(context: Context, _: Stage) -> None:
    if shutil.which("gh") is None:
        return
    try:
        active = json.loads(
            await gh(
                "run",
                "list",
                "--workflow",
                "extract.yml",
                "--limit",
                "20",
                "--json",
                "status,databaseId",
            )
        )
        if any(run["status"] != "completed" for run in active):
            return
        for run in active:
            saved = await checkpoints.get(
                context.pool, "extract-run", str(run["databaseId"])
            )
            if not (saved and saved.done):
                return
        queued = await run_plan(0)
        if queued < MIN_QUEUE:
            return
        shards = min(MAX_SHARDS, math.ceil(queued / REPOS_PER_SHARD))
        await gh("workflow", "run", "extract.yml", "-f", f"shards={shards}")
        context.items += queued
        log.info("dispatched %s repos over %s shards", queued, shards)
    except RuntimeError as error:
        context.errors += 1
        log.warning("could not dispatch an extract run: %s", error)
