SELECT
    d.network,
    d.contract_id,
    d.executable,
    d.wasm_hash,
    d.live,
    d.live_until_ledger,
    w.size AS wasm_size,
    w.sdk_version,
    w.source_repo,
    w.function_names,
    (
        SELECT sum(a.invocations) FROM contract_activity AS a
        WHERE a.network = d.network AND a.contract_id = d.contract_id
    ) AS invocations
FROM deployed_contracts AS d
LEFT JOIN wasm_modules AS w ON d.network = w.network AND d.wasm_hash = w.hash
WHERE d.network = $1 AND d.contract_id = $2
