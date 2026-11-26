INSERT INTO tools (name, repo, downloads, dependents)
VALUES ($1, $2, $3, $4)
ON CONFLICT (name) DO UPDATE SET
    repo = excluded.repo,
    downloads = excluded.downloads,
    dependents = excluded.dependents,
    resolved_at = now()
