SELECT r.full_name
FROM repos AS r
WHERE
    (r.is_soroban OR r.is_stellar)
    AND NOT r.is_fork
    AND (
        $1::boolean
        OR NOT EXISTS (
            SELECT 1 FROM checkpoints AS c
            WHERE
                c.job = 'history'
                AND c.key = r.full_name
                AND (c.status = 'done' OR (c.status = 'failed' AND c.attempts >= 3))
        )
    )
ORDER BY r.window_commits DESC NULLS LAST
