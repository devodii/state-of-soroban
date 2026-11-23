INSERT INTO crate_dependencies (
    repo, crate_path, kind, name, requirement, source, git_url, local_path,
    features, optional
)
VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
ON CONFLICT (repo, crate_path, kind, name) DO NOTHING
