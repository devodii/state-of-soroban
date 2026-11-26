import logging

from state_of_soroban import checkpoints
from state_of_soroban.linking.repo_ref import normalize_repo
from state_of_soroban.resilience import resilient
from state_of_soroban.runner import Context, stage
from state_of_soroban.sources.crates_io import Throttle, crate_repository
from state_of_soroban.sql_loader import load_sql
from state_of_soroban.workflow import Stage

log = logging.getLogger("state_of_soroban")

JOB = "tool"


@stage("tools.resolve")
async def resolve(context: Context, _: Stage) -> None:
    throttle = Throttle()
    rows = await context.pool.fetch(
        load_sql("tool_candidates"), context.workflow.tools.min_dependents
    )
    for row in rows:
        name = row["name"]
        saved = await checkpoints.get(context.pool, JOB, name)
        if saved and saved.done:
            continue
        found = await resilient(
            context.http,
            lambda name=name: crate_repository(context.http, throttle, name),
        )
        repo = normalize_repo(found.repo) if found.repo else None
        await context.pool.execute(
            load_sql("tool_put"), name, repo, found.downloads, row["dependents"]
        )
        await checkpoints.put(context.pool, JOB, name, "done", {"repo": repo})
        context.items += 1
    log.info("tools: %s crates resolved to repositories", context.items)
