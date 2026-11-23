SELECT
    network,
    count(*) AS contracts,
    count(*) FILTER (WHERE live) AS live
FROM deployed_contracts
GROUP BY network
