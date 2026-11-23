INSERT INTO graph_nodes (id, kind, label, props)
SELECT
    'bug:' || id,
    'bug_class',
    name,
    jsonb_build_object('severity', severity, 'weight', 3)
FROM bug_classes
