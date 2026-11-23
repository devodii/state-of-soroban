INSERT INTO contract_calls (
    repo, path, start_byte, line, caller_fn, kind, callee, method, target
)
VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
ON CONFLICT (repo, path, start_byte) DO NOTHING
