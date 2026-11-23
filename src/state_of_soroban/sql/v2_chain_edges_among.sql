SELECT
    e.network,
    e.caller,
    e.callee,
    sum(e.calls) AS calls
FROM contract_edges AS e
INNER JOIN unnest($1::text[], $2::text[]) AS t (network, caller) ON e.network = t.network AND e.caller = t.caller
WHERE e.callee = any($3::text[])
GROUP BY e.network, e.caller, e.callee
