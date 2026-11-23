SELECT
    network,
    contract_id,
    live
FROM deployed_contracts
WHERE contract_id ILIKE $1
ORDER BY contract_id ASC
LIMIT 5
