INSERT INTO graph_nodes (id, kind, label, props)
SELECT DISTINCT ON (best.id)
    best.id,
    'contract',
    left(best.contract_id, 8),
    jsonb_build_object('network', best.network, 'live', best.live, 'link', best.link, 'weight', 2)
FROM (
    SELECT
        'contract:' || l.network || ':' || l.contract_id AS id,
        l.contract_id,
        l.network,
        l.live,
        l.link,
        CASE l.link WHEN 'verified' THEN 1 WHEN 'deployment' THEN 2 ELSE 3 END AS rank
    FROM repo_contract_links AS l
    WHERE
        l.link IN ('verified', 'deployment', 'code')
        AND 'repo:' || l.repo IN (SELECT id FROM graph_nodes)
) AS best
ORDER BY best.id ASC, best.rank ASC
