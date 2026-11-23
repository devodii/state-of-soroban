SELECT
    full_name,
    size_kb,
    window_commits
FROM repos
WHERE
    pushed_at >= $1
    AND (languages ? $2 OR $2 = '')
    AND size_kb <= $3
    AND ($4::boolean OR scanned_at IS NULL)
    AND NOT EXISTS (
        SELECT 1 FROM checkpoints AS c
        WHERE
            c.job = 'extract'
            AND c.key = repos.full_name
            AND (c.status = 'gone' OR (c.status = 'failed' AND c.attempts >= 3))
    )
ORDER BY size_kb ASC, stars DESC
