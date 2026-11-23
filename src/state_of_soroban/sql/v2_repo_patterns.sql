SELECT
    m.pattern AS id,
    p.category,
    count(*) AS occurrences,
    min(m.path) AS sample_path,
    min(left(m.snippet, 500)) AS sample
FROM pattern_matches AS m
INNER JOIN patterns AS p ON m.pattern = p.id
WHERE m.repo = $1 AND NOT m.in_test
GROUP BY m.pattern, p.category
ORDER BY count(*) DESC
LIMIT $2
