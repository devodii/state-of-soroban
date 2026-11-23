INSERT INTO graph_edges (src, dst, kind, weight)
SELECT
    'proposal:' || pb.proposal,
    'bug:' || pb.bug_class,
    'prevents',
    2
FROM proposal_bug_classes AS pb
WHERE 'proposal:' || pb.proposal IN (SELECT id FROM graph_nodes)
