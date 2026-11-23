INSERT INTO graph_edges (src, dst, kind, weight)
SELECT
    'repo:' || l.repo,
    'contract:' || l.network || ':' || l.contract_id,
    'deploys',
    CASE l.link WHEN 'verified' THEN 4 WHEN 'deployment' THEN 3 ELSE 1 END
FROM repo_contract_links AS l
WHERE
    l.link IN ('verified', 'deployment', 'code')
    AND 'repo:' || l.repo IN (SELECT id FROM graph_nodes)
    AND 'contract:' || l.network || ':' || l.contract_id IN (SELECT id FROM graph_nodes)
