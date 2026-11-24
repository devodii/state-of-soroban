SELECT full_name
FROM repos
WHERE $1::boolean OR pushed_at IS NULL
ORDER BY full_name
