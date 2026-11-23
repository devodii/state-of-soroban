SELECT
    network,
    caller,
    callee,
    sum(calls) AS calls,
    sum(successful) AS successful,
    count(*) AS active_days
FROM contract_edges
GROUP BY network, caller, callee
ORDER BY sum(calls) DESC
LIMIT 200
