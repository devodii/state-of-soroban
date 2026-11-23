INSERT INTO graph_nodes (id, kind, label, props)
SELECT
    'proposal:' || top.id,
    'proposal',
    left(top.name, 80),
    jsonb_build_object('score', top.score, 'origin', top.origin, 'status', top.status, 'weight', top.score)
FROM (
    SELECT
        p.id,
        p.name,
        p.score,
        p.origin,
        p.status
    FROM proposals AS p
    ORDER BY p.score DESC
    LIMIT $1
) AS top
