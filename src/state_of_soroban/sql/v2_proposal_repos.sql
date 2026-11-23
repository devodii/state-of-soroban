SELECT
    pr.repo AS full_name,
    pr.weight,
    r.stars,
    r.language,
    r.description,
    r.networks,
    r.pushed_at,
    count(*) OVER () AS total
FROM proposal_repos AS pr
INNER JOIN repos AS r ON pr.repo = r.full_name
WHERE pr.proposal = $1 AND r.is_soroban
ORDER BY pr.weight DESC, r.stars DESC
LIMIT $2
