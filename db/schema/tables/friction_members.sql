CREATE TABLE friction_members (
    run_id text,
    kind text,
    repo text,
    ref text,
    cluster integer NOT NULL,
    sim real NOT NULL,
    CONSTRAINT friction_members_pkey PRIMARY KEY (run_id, kind, repo, ref),
    CONSTRAINT friction_members_run_fkey FOREIGN KEY (run_id) REFERENCES analysis_runs (run_id) ON DELETE CASCADE
);
