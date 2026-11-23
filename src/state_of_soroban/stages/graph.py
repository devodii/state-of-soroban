import logging

from state_of_soroban.runner import Context, stage
from state_of_soroban.sql_loader import load_sql
from state_of_soroban.workflow import Stage

log = logging.getLogger("state_of_soroban")

TOP_PROPOSALS = 25
MAX_REPOS = 1500


@stage("graph.build")
async def build_graph(context: Context, _: Stage) -> None:
    libraries = context.catalog.libraries
    ids = [lib.id for lib in libraries if lib.crates and lib.id != "soroban-sdk"]
    pairs = [
        (lib.id, crate) for lib in libraries if lib.id in ids for crate in lib.crates
    ]
    async with context.pool.acquire() as connection, connection.transaction():
        await connection.execute(load_sql("graph_reset"))
        await connection.execute(load_sql("graph_nodes_proposals"), TOP_PROPOSALS)
        await connection.execute(load_sql("graph_nodes_repos"), MAX_REPOS)
        await connection.execute(load_sql("graph_nodes_libraries"), ids)
        await connection.execute(load_sql("graph_nodes_bug_classes"))
        await connection.execute(load_sql("graph_nodes_contracts"))
        await connection.execute(load_sql("graph_edges_hand_rolls"))
        await connection.execute(load_sql("graph_edges_prevents"))
        await connection.execute(
            load_sql("graph_edges_libraries"),
            [p[0] for p in pairs],
            [p[1] for p in pairs],
        )
        await connection.execute(load_sql("graph_edges_proposal_library"))
        await connection.execute(load_sql("graph_edges_deploys"))
        await connection.execute(load_sql("graph_edges_calls"))
        nodes = await connection.fetchval("SELECT count(*) FROM graph_nodes")
        edges = await connection.fetchval("SELECT count(*) FROM graph_edges")
    context.items = nodes + edges
    context.detail.update({"nodes": nodes, "edges": edges})
    log.info("graph: %s nodes, %s edges", nodes, edges)
