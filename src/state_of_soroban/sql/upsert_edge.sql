INSERT INTO contract_edges (network, caller, callee, day, calls, successful, functions)
VALUES ($1, $2, $3, $4, $5, $6, $7)
ON CONFLICT (network, caller, callee, day) DO UPDATE SET
    calls = excluded.calls,
    successful = excluded.successful,
    functions = excluded.functions
