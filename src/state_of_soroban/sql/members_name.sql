SELECT DISTINCT
    repo,
    path
FROM functions
WHERE lower(name) = $1 AND NOT is_test
