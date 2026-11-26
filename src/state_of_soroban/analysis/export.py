import asyncio
import logging
import tempfile
from pathlib import Path

from state_of_soroban.analysis.records import RepoText, Unit, write_jsonl
from state_of_soroban.analysis.text import clean_text, repo_text
from state_of_soroban.config import ROOT
from state_of_soroban.database import open_pool
from state_of_soroban.extract.plan import git
from state_of_soroban.sql_loader import load_sql
from state_of_soroban.workflow import load_workflow

log = logging.getLogger("state_of_soroban")


async def export_units() -> int:
    workflow = load_workflow()
    limit = workflow.analysis.text_chars
    pool = await open_pool(2)
    try:
        rows = await pool.fetch(load_sql("analysis_units"))
        repo_rows = await pool.fetch(load_sql("analysis_repos"))
    finally:
        await pool.close()
    units = [
        Unit(
            id=f"{row['kind']}|{row['repo']}|{row['ref']}",
            text=clean_text(row["title"], row["body"], limit),
            family=row["family"],
            owner=row["owner"],
        )
        for row in rows
    ]
    units = [unit for unit in units if len(unit.text) >= 12]
    repos = [
        RepoText(
            repo=row["full_name"],
            text=repo_text(row["description"], row["topics"] or [], row["readme"], 500),
        )
        for row in repo_rows
    ]
    repos = [repo for repo in repos if len(repo.text) >= 25]
    remote = await git("remote", "get-url", "origin", cwd=ROOT)
    with tempfile.TemporaryDirectory(prefix="sw-analysis-") as folder:
        root = Path(folder)
        await git("init", "-q", "-b", "analysis", cwd=root)
        write_jsonl(root / "units.jsonl.gz", units)
        write_jsonl(root / "repos.jsonl.gz", repos)
        await git("add", ".", cwd=root)
        await git(
            "-c",
            "user.name=analysis",
            "-c",
            "user.email=analysis@localhost",
            "commit",
            "-q",
            "-m",
            f"chore: {len(units)} evidence units",
            cwd=root,
        )
        await git("push", "-q", "-f", remote, "analysis", cwd=root)
    log.info("published %s evidence units on the analysis branch", len(units))
    return len(units)


def run_export() -> int:
    return asyncio.run(export_units())
