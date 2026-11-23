UPDATE stage_runs
SET
    finished_at = now(),
    status = $2,
    items = $3,
    errors = $4,
    detail = $5
WHERE id = $1
