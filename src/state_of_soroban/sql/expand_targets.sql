SELECT r.full_name
FROM repos AS r
WHERE
    (r.is_soroban OR r.is_stellar)
    AND NOT r.is_fork
    AND ($2 = 'contributors' OR r.forks > 0)
    AND (
        $1::boolean
        OR NOT EXISTS (
            SELECT 1 FROM checkpoints AS c
            WHERE c.job = $2 AND c.key = r.full_name AND c.status = 'done'
        )
    )
ORDER BY r.stars DESC NULLS LAST
