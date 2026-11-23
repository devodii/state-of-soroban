SELECT
    id,
    author,
    body,
    created_at
FROM comments
WHERE target_kind = $1 AND target_id = $2
ORDER BY created_at DESC
