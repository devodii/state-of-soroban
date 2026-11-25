CREATE TABLE evidence (
    kind text,
    repo text,
    ref text,
    family text NOT NULL,
    owner text NOT NULL,
    author_login text,
    occurred_at timestamptz,
    title text NOT NULL,
    body text,
    url text NOT NULL,
    layers text[] DEFAULT '{}' NOT NULL,
    files integer DEFAULT 0 NOT NULL,
    is_bot boolean DEFAULT FALSE NOT NULL,
    dup_key text NOT NULL,
    dup_owners integer DEFAULT 1 NOT NULL,
    CONSTRAINT evidence_pkey PRIMARY KEY (kind, repo, ref)
);
