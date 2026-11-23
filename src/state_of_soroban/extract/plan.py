import asyncio
import json
import logging
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from state_of_soroban.catalog import active_patterns, load_catalog
from state_of_soroban.config import ROOT
from state_of_soroban.database import open_pool
from state_of_soroban.sql_loader import load_sql
from state_of_soroban.workflow import load_workflow

log = logging.getLogger("state_of_soroban")


async def git(*args: str, cwd: Path) -> str:
    process = await asyncio.create_subprocess_exec(
        "git",
        *args,
        cwd=cwd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    out, _ = await process.communicate()
    if process.returncode != 0:
        raise RuntimeError(out.decode(errors="replace")[:300])
    return out.decode().strip()


async def run_plan(limit: int) -> int:
    workflow = load_workflow()
    catalog = load_catalog(workflow)
    pool = await open_pool(2)
    try:
        cutoff = datetime.combine(
            workflow.window.start, datetime.min.time(), tzinfo=UTC
        )
        rows = await pool.fetch(
            load_sql("scan_targets"),
            cutoff,
            workflow.clone.require_language or "",
            workflow.clone.max_repo_kb,
            False,
        )
        names = [row["full_name"] for row in rows]
        if limit:
            names = names[:limit]
        patterns = await active_patterns(pool, catalog)
    finally:
        await pool.close()
    remote = await git("remote", "get-url", "origin", cwd=ROOT)
    with tempfile.TemporaryDirectory(prefix="sw-queue-") as folder:
        root = Path(folder)
        await git("init", "-q", "-b", "queue", cwd=root)
        (root / "targets.txt").write_text("\n".join(names) + "\n")
        (root / "patterns.json").write_text(
            json.dumps([p.model_dump(mode="json") for p in patterns])
        )
        await git("add", ".", cwd=root)
        await git(
            "-c",
            "user.name=queue",
            "-c",
            "user.email=queue@localhost",
            "commit",
            "-q",
            "-m",
            f"chore: queue of {len(names)} repos",
            cwd=root,
        )
        await git("push", "-q", "-f", remote, "queue", cwd=root)
    log.info("queued %s repos on the queue branch", len(names))
    return len(names)
