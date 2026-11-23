SELECT
    p.id,
    p.category,
    count(DISTINCT m.repo) AS repos,
    count(m.pattern) AS occurrences,
    (
        SELECT count(*) FROM repos AS s
        WHERE s.is_soroban
    ) AS soroban_repos,
    (
        SELECT count(*) FROM functions AS f
        WHERE NOT f.is_test
    ) AS functions
FROM patterns AS p
LEFT JOIN pattern_matches AS m ON p.id = m.pattern AND NOT m.in_test
WHERE p.status = 'active'
GROUP BY p.id, p.category
