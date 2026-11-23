INSERT INTO repos (full_name, url, owner, discovered_via, crates_io_names)
SELECT DISTINCT ON (lower(name))
    name,
    'https://github.com/' || name,
    split_part(name, '/', 1),
    ARRAY['chain:source_repo'],
    '{}'::text[]
FROM (
    SELECT regexp_replace(source_repo, '^(https?://)?(www\.)?github\.com/|^github:|\.git$|/$', '', 'gi') AS name
    FROM wasm_modules
    WHERE source_repo IS NOT NULL
) AS linked
WHERE name ~ '^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$'
ON CONFLICT (full_name) DO UPDATE SET
    discovered_via = (
        SELECT coalesce(array_agg(DISTINCT via ORDER BY via), '{}')
        FROM unnest(repos.discovered_via || excluded.discovered_via) AS via
    )
