INSERT INTO ecosystem_dependencies (repo, ecosystem, path, name, kind, requirement)
VALUES ($1, $2, $3, $4, $5, $6)
ON CONFLICT (repo, ecosystem, path, name, kind) DO NOTHING
