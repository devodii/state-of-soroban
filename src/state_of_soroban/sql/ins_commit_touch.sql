INSERT INTO commit_pattern_touches (repo, sha, pattern, added, removed)
VALUES ($1, $2, $3, $4, $5)
ON CONFLICT (repo, sha, pattern) DO NOTHING
