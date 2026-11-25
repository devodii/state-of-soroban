CREATE TABLE analysis_runs (
    run_id text PRIMARY KEY,
    created_at timestamptz DEFAULT now() NOT NULL,
    source_count integer NOT NULL,
    metrics jsonb NOT NULL
);
