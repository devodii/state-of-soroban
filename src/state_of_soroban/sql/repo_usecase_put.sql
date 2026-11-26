INSERT INTO repo_usecases (run_id, repo, usecase, sim)
VALUES ($1, $2, $3, $4)
ON CONFLICT (run_id, repo) DO NOTHING
