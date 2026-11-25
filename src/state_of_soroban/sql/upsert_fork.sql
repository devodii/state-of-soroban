INSERT INTO repos (
    full_name, url, owner, discovered_via, crates_io_names, is_fork,
    parent_full_name
)
VALUES ($1, $2, $3, $4, $5, TRUE, $6)
ON CONFLICT (full_name) DO UPDATE SET
    is_fork = TRUE,
    parent_full_name = excluded.parent_full_name,
    discovered_via = (
        SELECT coalesce(array_agg(DISTINCT via ORDER BY via), '{}')
        FROM unnest(repos.discovered_via || excluded.discovered_via) AS via
    )
