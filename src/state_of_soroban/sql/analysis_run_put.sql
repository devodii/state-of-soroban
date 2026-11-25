INSERT INTO analysis_runs (run_id, source_count, metrics)
VALUES ($1, $2, $3)
ON CONFLICT (run_id) DO UPDATE SET source_count = excluded.source_count, metrics = excluded.metrics
