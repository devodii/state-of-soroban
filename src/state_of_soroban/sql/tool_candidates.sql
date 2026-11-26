SELECT
    d.name,
    count(DISTINCT d.repo) AS dependents
FROM crate_dependencies AS d
INNER JOIN repos AS r ON d.repo = r.full_name
WHERE
    r.is_soroban AND NOT r.is_fork
    AND d.source = 'registry' AND d.local_path IS NULL
GROUP BY d.name
HAVING count(DISTINCT d.repo) >= $1
ORDER BY dependents DESC
