SELECT
    g.id,
    g.kind,
    g.label,
    g.props,
    r.stars,
    r.pushed_at,
    r.networks,
    r.language,
    p.score AS proposal_score,
    p.status,
    p.origin,
    d.live
FROM graph_nodes AS g
LEFT JOIN repos AS r ON g.kind = 'repo' AND g.id = 'repo:' || r.full_name
LEFT JOIN proposals AS p ON g.kind = 'proposal' AND g.id = 'proposal:' || p.id
LEFT JOIN deployed_contracts AS d
    ON g.kind = 'contract' AND g.id = 'contract:' || d.network || ':' || d.contract_id
