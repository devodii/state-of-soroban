SELECT
    repo,
    number,
    kind,
    title,
    state,
    author_login,
    labels,
    comments,
    created_at,
    is_bug,
    url
FROM issues
WHERE
    ($1 = '' OR repo = $1)
    AND ($2 = '' OR search @@ websearch_to_tsquery('english', $2))
    AND (NOT $3::boolean OR is_bug)
    AND ($4 = '' OR kind = $4)
ORDER BY created_at DESC
LIMIT $5 OFFSET $6
