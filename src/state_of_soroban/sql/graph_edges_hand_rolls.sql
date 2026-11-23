INSERT INTO graph_edges (src, dst, kind, weight)
SELECT
    'repo:' || pr.repo,
    'proposal:' || pr.proposal,
    'hand_rolls',
    pr.weight
FROM proposal_repos AS pr
WHERE
    'repo:' || pr.repo IN (SELECT id FROM graph_nodes)
    AND 'proposal:' || pr.proposal IN (SELECT id FROM graph_nodes)
