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
    r.size_kb,
    cardinality(r.discovered_via) AS sources,
    (
        SELECT count(*) FROM pattern_matches AS pm
        WHERE pm.repo = r.full_name AND NOT pm.in_test
    ) AS pattern_hits,
    (
        SELECT count(*) FROM comments AS c
        WHERE c.target_kind = 'repo' AND c.target_id = r.full_name
    ) AS comments
FROM repos AS r
ORDER BY r.is_soroban DESC, r.window_commits DESC NULLS LAST, r.stars DESC
LIMIT $1
