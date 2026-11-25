SELECT full_name
FROM repos
WHERE $1::boolean OR pushed_at IS NULL
ORDER BY is_fork ASC, discovered_at DESC NULLS LAST
LIMIT $2
