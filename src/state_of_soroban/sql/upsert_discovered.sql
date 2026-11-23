INSERT INTO repos (full_name, url, owner, discovered_via, crates_io_names)
VALUES ($1, $2, $3, $4, $5)
ON CONFLICT (full_name) DO UPDATE SET
    discovered_via = (
        SELECT coalesce(array_agg(DISTINCT via ORDER BY via), '{}')
        FROM unnest(repos.discovered_via || excluded.discovered_via) AS via
    ),
    crates_io_names = (
        SELECT coalesce(array_agg(DISTINCT crate ORDER BY crate), '{}')
        FROM unnest(repos.crates_io_names || excluded.crates_io_names) AS crate
    )
