SELECT
    r.full_name,
    r.url,
    r.owner,
    r.description,
    r.homepage,
    r.topics,
    r.language,
    r.license,
    r.stars,
    r.forks,
    r.open_issues,
    r.size_kb,
    r.archived,
    r.is_fork,
    r.created_at,
    r.pushed_at,
    r.networks,
    r.window_commits,
    r.total_commits,
    r.is_soroban,
    r.is_stellar,
    r.rust_files,
    r.rust_loc,
    r.contract_crates,
    r.stack,
    r.stellar_libs,
    r.languages,
    (
        SELECT count(*) FROM comments AS c
        WHERE c.target_kind = 'repo' AND c.target_id = r.full_name
    ) AS comments
FROM repos AS r
WHERE r.full_name = $1
