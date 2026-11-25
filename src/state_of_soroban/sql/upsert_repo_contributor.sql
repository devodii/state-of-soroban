INSERT INTO repo_contributors (repo, login, contributions)
VALUES ($1, $2, $3)
ON CONFLICT (repo, login) DO UPDATE SET contributions = excluded.contributions
