INSERT INTO commit_files (repo, sha, path, status, previous_path)
VALUES ($1, $2, $3, $4, $5)
ON CONFLICT (repo, sha, path) DO NOTHING
