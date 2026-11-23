UPDATE repos AS r
SET
    networks = (
        SELECT coalesce(array_agg(DISTINCT n ORDER BY n), '{}')
        FROM unnest(r.networks || found.networks) AS n
    )
FROM (
    SELECT
        refs.repo,
        array_agg(DISTINCT refs.network) AS networks
    FROM repo_contract_refs AS refs
    INNER JOIN deployed_contracts AS d
        ON refs.contract_id = d.contract_id AND refs.network = d.network
    GROUP BY refs.repo
) AS found
WHERE r.full_name = found.repo
