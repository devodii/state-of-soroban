CREATE TABLE repo_families (
    repo text PRIMARY KEY,
    family text NOT NULL,
    members integer NOT NULL,
    CONSTRAINT repo_families_repo_fkey FOREIGN KEY (repo) REFERENCES repos (full_name) ON DELETE CASCADE
);
