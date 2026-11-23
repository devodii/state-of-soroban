SELECT
    r.full_name,
    r.stars,
    r.pushed_at,
    r.window_commits,
    r.is_soroban,
    r.networks,
    r.rust_loc,
    r.contract_crates,
    r.language,
    r.description,
    (
        SELECT count(*) FROM pattern_matches AS pm
        WHERE pm.repo = r.full_name AND NOT pm.in_test
    ) AS pattern_hits,
    (
        SELECT array_agg(p.name ORDER BY p.score DESC)
        FROM proposal_repos AS pr
        INNER JOIN proposals AS p ON pr.proposal = p.id
        WHERE pr.repo = r.full_name
    ) AS proposals
FROM repos AS r
WHERE r.full_name = $1
