INSERT INTO graph_nodes (id, kind, label, props)
SELECT
    'repo:' || r.full_name,
    'repo',
    r.full_name,
    jsonb_build_object('stars', r.stars, 'networks', r.networks, 'weight', 1 + ln(1 + r.stars))
FROM repos AS r
WHERE r.full_name IN (
    SELECT pr.repo
    FROM proposal_repos AS pr
    INNER JOIN graph_nodes AS g ON g.id = 'proposal:' || pr.proposal
    INNER JOIN repos AS rr ON pr.repo = rr.full_name
    GROUP BY pr.repo, rr.stars
    ORDER BY count(*) DESC, rr.stars DESC
    LIMIT $1
)
