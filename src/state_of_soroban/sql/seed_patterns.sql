SELECT
    p.proposal,
    p.pattern,
    p.role
FROM proposal_patterns AS p
INNER JOIN proposals AS pr ON p.proposal = pr.id
WHERE pr.origin = 'seed'
ORDER BY p.proposal ASC
