SELECT
    substr(m, 5) AS macro,
    count(DISTINCT r.owner) AS owners,
    count(DISTINCT s.repo) AS repos,
    count(*) AS occurrences,
    (array_agg(s.repo ORDER BY s.loc DESC))[1] AS sample_repo,
    (array_agg(s.path ORDER BY s.loc DESC))[1] AS sample_path
FROM source_files AS s
INNER JOIN repos AS r ON s.repo = r.full_name
CROSS JOIN LATERAL unnest(s.macros) AS m
WHERE m LIKE 'def:%' AND NOT s.is_test AND NOT r.is_fork
GROUP BY substr(m, 5)
HAVING count(DISTINCT r.owner) >= $1
ORDER BY count(DISTINCT r.owner) DESC, count(*) DESC
LIMIT $2
