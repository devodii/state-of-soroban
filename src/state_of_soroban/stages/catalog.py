import logging

from state_of_soroban.runner import Context, stage
from state_of_soroban.sql_loader import load_sql
from state_of_soroban.workflow import Stage

log = logging.getLogger("state_of_soroban")


async def sync_needs(context: Context) -> None:
    catalog = context.catalog
    async with context.pool.acquire() as connection, connection.transaction():
        for tool in catalog.tools:
            await connection.execute(
                load_sql("upsert_tool"),
                tool.id,
                tool.name,
                tool.category,
                tool.url,
                tool.description,
                tool.ecosystems,
                tool.packages,
                tool.keywords,
                tool.solves,
            )
        for need in catalog.needs:
            await connection.execute(
                load_sql("upsert_seed_need"),
                need.id,
                need.title,
                need.category,
                need.summary,
                need.query,
                need.signals.model_dump(),
                {},
            )
        await connection.execute(load_sql("clear_seed_need_tools"))
        for need in catalog.needs:
            for link in need.tools:
                await connection.execute(
                    load_sql("link_need_tool"), need.id, link.id, link.relation, 1.0
                )
        await connection.execute(
            "DELETE FROM tooling_needs WHERE origin = 'seed' AND id <> ALL($1::text[])",
            [n.id for n in catalog.needs],
        )
        await connection.execute(
            "DELETE FROM tool_catalog WHERE origin = 'seed' AND id <> ALL($1::text[])",
            [t.id for t in catalog.tools],
        )
    log.info("needs: %s themes, %s tools", len(catalog.needs), len(catalog.tools))


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
        await connection.executemany(
            load_sql("catalog_upsert_proposal"),
            [
                (
                    p.id,
                    p.name,
                    p.kind,
                    p.summary,
                    p.sketch,
                    p.thresholds.min_repos,
                    p.thresholds.min_share,
                    p.thresholds.min_occurrences,
                    p.covered_by,
                )
                for p in catalog.proposals
            ],
        )
        await connection.execute(
            "DELETE FROM proposal_patterns WHERE proposal IN "
            "(SELECT id FROM proposals WHERE origin = 'seed')"
        )
        await connection.execute(
            "DELETE FROM proposal_bug_classes WHERE proposal IN "
            "(SELECT id FROM proposals WHERE origin = 'seed')"
        )
        await connection.executemany(
            load_sql("catalog_link_pattern"),
            [
                (p.id, item.id, item.role)
                for p in catalog.proposals
                for item in p.patterns
            ],
        )
        await connection.executemany(
            load_sql("catalog_link_bug_class"),
            [(p.id, bug) for p in catalog.proposals for bug in p.bug_classes],
        )
        await connection.execute(
            "DELETE FROM proposals WHERE origin = 'seed' AND id <> ALL($1::text[])",
            [p.id for p in catalog.proposals],
        )
        await connection.execute(
            "DELETE FROM patterns WHERE origin = 'seed' AND id <> ALL($1::text[])",
            [p.id for p in catalog.patterns],
        )
        await connection.execute(
            "DELETE FROM bug_classes WHERE id <> ALL($1::text[])",
            [b.id for b in catalog.bug_classes],
        )
    context.items = len(catalog.patterns) + len(catalog.proposals)
    await sync_needs(context)
    log.info(
        "catalog: %s patterns, %s bug classes, %s proposals",
        len(catalog.patterns),
        len(catalog.bug_classes),
        len(catalog.proposals),
    )
