INSERT INTO repo_contract_refs (repo, path, contract_id, network, line)
VALUES ($1, $2, $3, $4, $5)
ON CONFLICT (repo, path, contract_id) DO NOTHING
