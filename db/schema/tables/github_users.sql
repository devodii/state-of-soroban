CREATE TABLE github_users (
    login text PRIMARY KEY,
    avatar_url text NOT NULL,
    html_url text,
    user_type text,
    seen_at timestamptz DEFAULT now() NOT NULL
);
