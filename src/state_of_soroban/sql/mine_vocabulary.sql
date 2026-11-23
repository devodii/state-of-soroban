SELECT
    member ->> 'name' AS name,
    count(DISTINCT r.owner) AS owners,
    count(DISTINCT t.repo) AS repos,
    count(*) AS occurrences
FROM type_defs AS t
INNER JOIN repos AS r ON t.repo = r.full_name
INNER JOIN source_files AS s ON t.repo = s.repo AND t.path = s.path
CROSS JOIN LATERAL jsonb_array_elements(t.members) AS member
WHERE
    NOT s.is_test
    AND NOT r.is_fork
    AND t.kind = 'enum'
    AND (
        ($1 = 'errors' AND t.is_contracterror)
        OR ($1 = 'keys' AND t.is_contracttype AND t.name ~* 'key')
    )
GROUP BY member ->> 'name'
HAVING count(DISTINCT r.owner) >= $2
ORDER BY count(DISTINCT r.owner) DESC, count(*) DESC
LIMIT $3
