SELECT
    p.id,
    p.name,
    p.score,
    p.status,
    p.origin,
    pr.weight
FROM proposal_repos AS pr
INNER JOIN proposals AS p ON pr.proposal = p.id
WHERE pr.repo = $1
ORDER BY p.score DESC
LIMIT $2
