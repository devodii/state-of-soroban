INSERT INTO graph_edges (src, dst, kind, weight)
SELECT
    'proposal:' || p.id,
    'lib:' || c.library,
    'covered_by',
    2
FROM proposals AS p
CROSS JOIN LATERAL unnest(p.covered_by) AS c (library)
WHERE
    'proposal:' || p.id IN (SELECT id FROM graph_nodes)
    AND 'lib:' || c.library IN (SELECT id FROM graph_nodes)
