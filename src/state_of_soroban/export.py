import json
from pathlib import Path

from state_of_soroban.api import UI_DIR, overview, records
from state_of_soroban.database import open_pool
from state_of_soroban.sql_loader import load_sql

MARKER = "load(); setInterval"


async def run_export(out: str) -> None:
    pool = await open_pool()
    try:
        data = await overview(pool, 5000)
        async with pool.acquire() as connection:
            graph = {
                "nodes": records(await connection.fetch(load_sql("graph_nodes"))),
                "edges": records(await connection.fetch(load_sql("graph_edges"))),
            }
    finally:
        await pool.close()
    target = Path(out)
    target.mkdir(parents=True, exist_ok=True)
    payload = json.dumps({"overview": data, "graph": graph}, default=str)
    (target / "data.json").write_text(payload)
    shim = (
        "const SNAPSHOT = " + payload + ";\n"
        "const realFetch = window.fetch;\n"
        "window.fetch = (url) => Promise.resolve({ json: () => Promise.resolve("
        "String(url).includes('/api/graph') ? SNAPSHOT.graph : "
        "String(url).includes('/api/comments') ? [] : SNAPSHOT.overview) });\n"
    )
    html = (UI_DIR / "index.html").read_text().replace(MARKER, shim + MARKER, 1)
    (target / "index.html").write_text(html.replace("setInterval(", "void(", 1))
    print(f"wrote {target}/data.json and {target}/index.html")
