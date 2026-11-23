INSERT INTO repo_contributors (
    repo, login, contributions, window_commits, first_commit_at, last_commit_at
)
VALUES ($1, $2, $3, $3, $4, $5)
ON CONFLICT (repo, login) DO NOTHING
