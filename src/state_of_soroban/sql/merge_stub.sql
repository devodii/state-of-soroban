UPDATE repos
SET
    discovered_via = (
        SELECT coalesce(array_agg(DISTINCT via ORDER BY via), '{}')
        FROM unnest(repos.discovered_via || stub.discovered_via) AS via
    ),
    crates_io_names = (
        SELECT coalesce(array_agg(DISTINCT crate ORDER BY crate), '{}')
        FROM unnest(repos.crates_io_names || stub.crates_io_names) AS crate
    )
FROM repos AS stub
WHERE repos.full_name = $2 AND stub.full_name = $1
