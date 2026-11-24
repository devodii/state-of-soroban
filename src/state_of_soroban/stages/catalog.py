import logging

from state_of_soroban.runner import Context, stage
from state_of_soroban.sql_loader import load_sql
from state_of_soroban.workflow import Stage

log = logging.getLogger("state_of_soroban")


@stage("catalog.sync")
async def sync_catalog(context: Context, _: Stage) -> None:
    catalog = context.catalog
    async with context.pool.acquire() as connection, connection.transaction():
        await connection.executemany(
            load_sql("catalog_upsert_pattern"),
            [
                (p.id, p.category, p.description, p.match.model_dump_json())
                for p in catalog.patterns
            ],
        )
        await connection.executemany(
            load_sql("catalog_upsert_bug_class"),
            [(b.id, b.name, b.description, b.severity) for b in catalog.bug_classes],
        )
        await connection.execute(
            "DELETE FROM patterns WHERE origin = 'seed' AND id <> ALL($1::text[])",
            [p.id for p in catalog.patterns],
        )
        await connection.execute(
            "DELETE FROM bug_classes WHERE id <> ALL($1::text[])",
            [b.id for b in catalog.bug_classes],
        )
    context.items = len(catalog.patterns)
    log.info(
        "catalog: %s patterns, %s bug classes",
        len(catalog.patterns),
        len(catalog.bug_classes),
    )
