CREATE TABLE repo_usecases (
    run_id text,
    repo text,
    usecase integer NOT NULL,
    sim real NOT NULL,
    CONSTRAINT repo_usecases_pkey PRIMARY KEY (run_id, repo),
    CONSTRAINT repo_usecases_run_fkey FOREIGN KEY (run_id) REFERENCES analysis_runs (run_id) ON DELETE CASCADE
);
