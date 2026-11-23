SELECT
    r.full_name,
    r.stars,
    r.pushed_at,
    r.networks,
    r.language,
    pr.weight
FROM proposal_repos AS pr
INNER JOIN repos AS r ON pr.repo = r.full_name
WHERE pr.proposal = $1 AND r.is_soroban
ORDER BY pr.weight DESC, r.stars DESC
LIMIT $2
