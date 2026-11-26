CREATE TABLE usecases (
    run_id text,
    usecase integer,
    size integer NOT NULL,
    terms text[] NOT NULL,
    CONSTRAINT usecases_pkey PRIMARY KEY (run_id, usecase),
    CONSTRAINT usecases_run_fkey FOREIGN KEY (run_id) REFERENCES analysis_runs (run_id) ON DELETE CASCADE
);
