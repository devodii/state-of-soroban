INSERT INTO graph_nodes (id, kind, label, props)
SELECT
    'lib:' || l.id,
    'library',
    l.id,
    jsonb_build_object('weight', 3)
FROM (SELECT unnest($1::text[]) AS id) AS l
