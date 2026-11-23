SELECT
    repo,
    path
FROM source_files
WHERE $1 = ANY(macros) AND NOT is_test
