SELECT DISTINCT ON (stage)
    stage,
    status,
    items,
    errors,
    started_at,
    finished_at,
    extract(EPOCH FROM coalesce(finished_at, now()) - started_at) AS seconds
FROM stage_runs
ORDER BY stage ASC, started_at DESC
