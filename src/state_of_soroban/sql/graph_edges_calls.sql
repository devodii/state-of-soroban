INSERT INTO graph_edges (src, dst, kind, weight)
SELECT
    'contract:' || e.network || ':' || e.caller,
    'contract:' || e.network || ':' || e.callee,
    'calls',
    ln(1 + sum(e.calls))
FROM contract_edges AS e
WHERE
    'contract:' || e.network || ':' || e.caller IN (SELECT id FROM graph_nodes)
    AND 'contract:' || e.network || ':' || e.callee IN (SELECT id FROM graph_nodes)
GROUP BY e.network, e.caller, e.callee
