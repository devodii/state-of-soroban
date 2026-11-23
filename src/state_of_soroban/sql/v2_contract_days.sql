SELECT
    day,
    invocations,
    successful,
    callers
FROM contract_activity
WHERE network = $1 AND contract_id = $2
ORDER BY day ASC
