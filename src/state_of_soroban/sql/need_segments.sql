SELECT
    s AS stack,
    count(DISTINCT e.repo) AS repos
FROM need_evidence AS e
INNER JOIN repos AS r ON e.repo = r.full_name
CROSS JOIN LATERAL unnest(CASE WHEN cardinality(r.stack) = 0 THEN ARRAY['rust'] ELSE r.stack END) AS s
WHERE e.need = $1
GROUP BY s
ORDER BY count(DISTINCT e.repo) DESC
LIMIT 8
