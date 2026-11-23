UPDATE repo_contract_refs
SET network = $2
WHERE contract_id = $1
