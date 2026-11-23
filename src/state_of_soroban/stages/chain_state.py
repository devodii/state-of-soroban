import asyncio
import logging

from state_of_soroban.chain.rpc import (
    RpcClient,
    code_key,
    instance_key,
    read_code,
    read_instance,
)
from state_of_soroban.chain.wasm import read_wasm
from state_of_soroban.runner import Context, stage
from state_of_soroban.sql_loader import load_sql
from state_of_soroban.workflow import Stage

log = logging.getLogger("state_of_soroban")


def chunks(items: list, size: int) -> list[list]:
    return [items[i : i + size] for i in range(0, len(items), size)]


async def check_network(context: Context, network: str, ids: list[str]) -> int:
    config = context.workflow.chain
    rpc = RpcClient(context.http, config.network(network).rpc_urls)
    gate = asyncio.Semaphore(config.rpc.concurrency)
    instances = {}

    async def look(batch: list[str]) -> None:
        keys = {instance_key(cid): cid for cid in batch}
        async with gate:
            found = await rpc.entries(list(keys))
        for key, entry in found.items():
            cid = keys[key]
            instances[cid] = read_instance(cid, entry)

    await asyncio.gather(*(look(b) for b in chunks(ids, config.rpc.batch_keys)))
    async with context.pool.acquire() as connection:
        known = {
            row["hash"]
            for row in await connection.fetch(load_sql("known_wasm_hashes"), network)
        }
    wanted = sorted({i.wasm_hash for i in instances.values() if i.wasm_hash} - known)
    modules: dict[str, tuple] = {}

    async def fetch(batch: list[str]) -> None:
        keys = {code_key(h): h for h in batch}
        async with gate:
            found = await rpc.entries(list(keys))
        for key, wasm_hash in keys.items():
            entry = found.get(key)
            if entry is None:
                modules[wasm_hash] = (0, None, None, None, {"missing": True}, {})
                continue
            info = read_wasm(read_code(entry))
            modules[wasm_hash] = (
                info.size,
                info.sdk_version,
                info.rust_version,
                info.source_repo,
                info.meta,
                info.spec,
            )

    await asyncio.gather(*(fetch(b) for b in chunks(wanted, 20)))
    async with context.pool.acquire() as connection, connection.transaction():
        for wasm_hash, (size, sdk, rust, source, meta, spec) in modules.items():
            await connection.execute(
                load_sql("upsert_wasm_module"),
                wasm_hash,
                network,
                size,
                sdk,
                rust,
                source,
                meta,
                spec,
                [f["name"] for f in spec.get("functions", [])],
                len(spec.get("functions", [])),
                len(spec.get("events", [])),
                len(spec.get("errors", [])),
                len(spec.get("structs", []))
                + len(spec.get("unions", []))
                + len(spec.get("enums", [])),
            )
        for instance in instances.values():
            await connection.execute(
                load_sql("upsert_deployed_contract"),
                network,
                instance.contract_id,
                instance.executable,
                instance.wasm_hash,
                (instance.live_until or 0) >= rpc.latest,
                instance.live_until,
                rpc.latest,
            )
            await connection.execute(
                load_sql("confirm_ref_network"), instance.contract_id, network
            )
    log.info(
        "%s: %s of %s contracts exist, %s new wasm modules",
        network,
        len(instances),
        len(ids),
        len(modules),
    )
    return len(instances)


@stage("chain.state")
async def chain_state(context: Context, _: Stage) -> None:
    async with context.pool.acquire() as connection:
        ids = [
            row["contract_id"]
            for row in await connection.fetch(load_sql("contract_ref_ids"))
        ]
    if context.limit:
        ids = ids[: context.limit]
    for network in ("mainnet", "testnet"):
        if network in context.workflow.networks:
            context.items += await check_network(context, network, ids)
    async with context.pool.acquire() as connection:
        await connection.execute(load_sql("add_repo_networks"))
