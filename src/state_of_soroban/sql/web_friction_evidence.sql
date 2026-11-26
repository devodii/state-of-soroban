SELECT
    e.kind,
    e.repo,
    e.title,
    e.url,
    e.occurred_at,
    e.author_login,
    m.sim
FROM friction_members AS m
INNER JOIN evidence AS e ON m.kind = e.kind AND m.repo = e.repo AND m.ref = e.ref
WHERE
    m.run_id = (
        SELECT run_id FROM analysis_runs
        ORDER BY created_at DESC LIMIT 1
    )
    AND m.cluster = $1
    AND ($2 = '' OR e.kind = $2)
ORDER BY m.sim DESC
LIMIT $3 OFFSET $4
