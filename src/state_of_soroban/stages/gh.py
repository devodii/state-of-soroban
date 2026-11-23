import asyncio
import json
import logging

log = logging.getLogger("state_of_soroban")


async def gh(*args: str) -> str:
    process = await asyncio.create_subprocess_exec(
        "gh",
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    out, err = await process.communicate()
    if process.returncode != 0:
        raise RuntimeError(err.decode(errors="replace")[:300])
    return out.decode()


async def drop_artifacts(run_id: str) -> None:
    try:
        found = json.loads(
            await gh(
                "api",
                f"repos/devodii/state-of-soroban/actions/runs/{run_id}/artifacts",
                "--jq",
                "[.artifacts[].id]",
            )
        )
        for artifact in found:
            await gh(
                "api",
                "-X",
                "DELETE",
                f"repos/devodii/state-of-soroban/actions/artifacts/{artifact}",
            )
    except RuntimeError as error:
        log.warning("could not clean artifacts of run %s: %s", run_id, error)
