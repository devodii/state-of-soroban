SELECT full_name
FROM repos
WHERE
    pushed_at >= $1
    AND ecosystem_scanned_at IS NULL
    AND NOT is_fork
    AND NOT EXISTS (
        SELECT 1 FROM checkpoints AS c
        WHERE
            c.job = 'ecosystem'
            AND c.key = repos.full_name
            AND c.status = 'failed'
            AND c.attempts >= 3
    )
ORDER BY
    CASE
        WHEN EXISTS (
            SELECT 1 FROM unnest(discovered_via) AS v
            WHERE v NOT LIKE 'search:topic:%'
        ) THEN 0
        WHEN
            full_name || ' ' || coalesce(description, '') || ' ' || array_to_string(topics, ' ')
            ~* 'stellar|soroban|horizon|freighter|albedo|xlm|sep-?[0-9]+|lumens?'
            THEN 1
        ELSE 2
    END ASC,
    coalesce((SELECT bool_and(v LIKE 'owner:%') FROM unnest(discovered_via) AS v), FALSE) ASC,
    is_soroban DESC,
    stars DESC
