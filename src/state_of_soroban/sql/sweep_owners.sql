SELECT owner
FROM repos
WHERE
    is_soroban
    AND NOT is_fork
    AND (
        $1::boolean
        OR NOT EXISTS (
            SELECT 1 FROM checkpoints AS c
            WHERE c.job = 'sweep' AND c.key = repos.owner AND c.status = 'done'
        )
    )
GROUP BY owner
ORDER BY count(*) DESC
