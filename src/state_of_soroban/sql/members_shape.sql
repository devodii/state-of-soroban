SELECT DISTINCT
    repo,
    path
FROM functions
WHERE shape_hash = $1 AND NOT is_test
