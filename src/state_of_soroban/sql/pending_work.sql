SELECT
    count(*) FILTER (WHERE pushed_at IS NULL) AS metadata,
    count(*) FILTER (
        WHERE
        pushed_at >= $1
        AND (languages ? $2 OR $2 = '')
        AND size_kb <= $3
        AND scanned_at IS NULL
    ) AS clone,
    count(*) FILTER (
        WHERE
        is_soroban
        AND NOT EXISTS (
            SELECT 1 FROM checkpoints AS c
            WHERE c.job = 'history' AND c.key = repos.full_name AND c.status = 'done'
        )
    ) AS history
FROM repos
