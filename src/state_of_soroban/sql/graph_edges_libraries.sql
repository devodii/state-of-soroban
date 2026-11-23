INSERT INTO graph_edges (src, dst, kind, weight)
WITH l AS (
    SELECT
        t.id,
        t.crate
    FROM unnest($1::text[], $2::text[]) AS t (id, crate)
)

SELECT DISTINCT
    'repo:' || cd.repo,
    'lib:' || l.id,
    'uses_library',
    1
FROM crate_dependencies AS cd
INNER JOIN l ON cd.name = l.crate
WHERE 'repo:' || cd.repo IN (SELECT id FROM graph_nodes)
