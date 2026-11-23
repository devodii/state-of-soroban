INSERT INTO repo_network_signals (repo, path, network, signal, line, evidence)
VALUES ($1, $2, $3, $4, $5, $6)
ON CONFLICT (repo, path, network, signal, line) DO NOTHING
