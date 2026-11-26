CREATE TABLE tools (
    name text PRIMARY KEY,
    repo text,
    downloads bigint DEFAULT 0 NOT NULL,
    dependents integer DEFAULT 0 NOT NULL,
    resolved_at timestamptz DEFAULT now() NOT NULL
);
