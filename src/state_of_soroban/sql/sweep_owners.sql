WITH people AS (
    SELECT
        owner AS login,
        1 AS weight
    FROM repos
    WHERE is_soroban AND NOT is_fork
    UNION ALL
    SELECT
        rc.login,
        1 AS weight
    FROM repo_contributors AS rc
    INNER JOIN repos AS r ON rc.repo = r.full_name
    WHERE r.is_soroban AND NOT r.is_fork
)

SELECT login AS owner
FROM people AS p
WHERE
    $1::boolean
    OR NOT EXISTS (
        SELECT 1 FROM checkpoints AS c
        WHERE c.job = 'sweep' AND c.key = p.login AND c.status = 'done'
    )
GROUP BY login
HAVING
    count(*) >= $2 OR bool_or(login IN (
        SELECT owner FROM repos
        WHERE is_soroban
    ))
ORDER BY count(*) DESC
