INSERT INTO wasm_modules (
    hash, network, size, sdk_version, rust_version, source_repo, meta, spec,
    function_names, function_count, event_count, error_count, type_count
)
VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
ON CONFLICT (network, hash) DO UPDATE SET
    size = excluded.size,
    sdk_version = excluded.sdk_version,
    rust_version = excluded.rust_version,
    source_repo = excluded.source_repo,
    meta = excluded.meta,
    spec = excluded.spec,
    function_names = excluded.function_names,
    function_count = excluded.function_count,
    event_count = excluded.event_count,
    error_count = excluded.error_count,
    type_count = excluded.type_count,
    fetched_at = now()
