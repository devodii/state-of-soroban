INSERT INTO contract_activity (
    network, contract_id, day, invocations, successful, callers, functions
)
VALUES ($1, $2, $3, $4, $5, $6, $7)
ON CONFLICT (network, contract_id, day) DO UPDATE SET
    invocations = excluded.invocations,
    successful = excluded.successful,
    callers = excluded.callers,
    functions = excluded.functions
