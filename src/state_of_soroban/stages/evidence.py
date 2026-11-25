import logging

from state_of_soroban.runner import Context, stage
from state_of_soroban.sql_loader import load_sql
from state_of_soroban.workflow import Stage

log = logging.getLogger("state_of_soroban")


def find(parent: dict[str, str], item: str) -> str:
    parent.setdefault(item, item)
    while parent[item] != item:
        parent[item] = parent[parent[item]]
        item = parent[item]
    return item


async def build_families(context: Context) -> int:
    settings = context.workflow.evidence
    totals = {
        row["repo"]: row["total"]
        for row in await context.pool.fetch(load_sql("commit_totals"))
    }
    pairs = await context.pool.fetch(load_sql("families_pairs"), settings.min_shared)
    parent: dict[str, str] = {}
    for pair in pairs:
        smaller = min(totals[pair["left_repo"]], totals[pair["right_repo"]])
        if pair["shared"] / smaller >= settings.min_overlap:
            parent[find(parent, pair["left_repo"])] = find(parent, pair["right_repo"])
    groups: dict[str, list[str]] = {}
    for repo in list(parent):
        groups.setdefault(find(parent, repo), []).append(repo)
    rows = [
        (repo, root, len(members))
        for root, members in groups.items()
        for repo in members
    ]
    async with context.pool.acquire() as connection, connection.transaction():
        await connection.execute("TRUNCATE repo_families")
        await connection.executemany(
            "INSERT INTO repo_families (repo, family, members) VALUES ($1, $2, $3)",
            rows,
        )
    return len(groups)


@stage("evidence.build")
async def build(context: Context, _: Stage) -> None:
    families = await build_families(context)
    log.info("evidence: %s repo families", families)
    async with context.pool.acquire() as connection, connection.transaction():
        await connection.execute(load_sql("evidence_clear"))
        await connection.execute(load_sql("evidence_commits"))
        await connection.execute(load_sql("evidence_issues"))
        await connection.execute(load_sql("evidence_duplicates"))
        context.items = await connection.fetchval("SELECT count(*) FROM evidence")
    log.info("evidence: %s units", context.items)
