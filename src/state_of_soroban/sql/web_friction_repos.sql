SELECT
    e.family,
    min(e.repo) AS repo,
    count(*) AS units,
    max(e.occurred_at) AS last_seen
FROM friction_members AS m
INNER JOIN evidence AS e ON m.kind = e.kind AND m.repo = e.repo AND m.ref = e.ref
WHERE
    m.run_id = (
        SELECT run_id FROM analysis_runs
        ORDER BY created_at DESC LIMIT 1
    )
    AND m.cluster = $1
GROUP BY e.family
ORDER BY units DESC
LIMIT 15
