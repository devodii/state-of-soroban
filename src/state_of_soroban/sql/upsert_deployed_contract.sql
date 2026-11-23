INSERT INTO deployed_contracts (
    network, contract_id, executable, wasm_hash, live, live_until_ledger,
    observed_ledger
)
VALUES ($1, $2, $3, $4, $5, $6, $7)
ON CONFLICT (network, contract_id) DO UPDATE SET
    executable = excluded.executable,
    wasm_hash = excluded.wasm_hash,
    live = excluded.live,
    live_until_ledger = excluded.live_until_ledger,
    observed_ledger = excluded.observed_ledger,
    observed_at = now()
