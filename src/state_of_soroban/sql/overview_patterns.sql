SELECT
    p.id,
    p.category,
    p.description,
    count(DISTINCT m.repo) AS repos,
    count(m.pattern) AS occurrences
FROM patterns AS p
LEFT JOIN pattern_matches AS m ON p.id = m.pattern AND NOT m.in_test
GROUP BY p.id, p.category, p.description
ORDER BY repos DESC, occurrences DESC
