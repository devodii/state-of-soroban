SELECT
    r.full_name,
    r.description,
    r.is_soroban,
    r.is_fork,
    r.parent_full_name,
    r.stars,
    r.forks,
    r.archived,
    r.networks,
    r.discovered_via,
    (
        SELECT count(*) FROM commits AS c
        WHERE c.repo = r.full_name
    ) AS commit_count,
    (
        SELECT count(*) FROM commits AS c
        WHERE c.repo = r.full_name AND c.is_fix
    ) AS fix_count,
    (
        SELECT count(*) FROM issues AS i
        WHERE i.repo = r.full_name
    ) AS issue_count,
    (
        SELECT count(*) FROM functions AS f
        WHERE f.repo = r.full_name
    ) AS function_count,
    (
        SELECT count(*) FROM source_files AS s
        WHERE s.repo = r.full_name
    ) AS file_count
FROM repos AS r
WHERE r.full_name = $1
