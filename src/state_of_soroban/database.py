import json

import asyncpg

from state_of_soroban.config import get_settings


async def _init_connection(connection: asyncpg.Connection) -> None:
    await connection.set_type_codec(
        "jsonb", encoder=json.dumps, decoder=json.loads, schema="pg_catalog"
    )


async def open_pool(size: int = 10) -> asyncpg.Pool:
    return await asyncpg.create_pool(
        get_settings().database_url,
        min_size=1,
        max_size=size,
        init=_init_connection,
    )
