INSERT INTO commits (
    repo, sha, author_login, author_name, committed_at, message, parents,
    additions, deletions, files_changed, touches_rust, is_fix, bug_classes
)
VALUES ($1, $2, $3, $4, $5, $6, $7, 0, 0, $8, $9, $10, $11)
ON CONFLICT (repo, sha) DO NOTHING
