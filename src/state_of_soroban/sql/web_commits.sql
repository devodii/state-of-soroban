SELECT
    repo,
    sha,
    author_login,
    committed_at,
    message,
    additions,
    deletions,
    is_fix,
    bug_classes
FROM commits
WHERE
    ($1 = '' OR repo = $1)
    AND ($2 = '' OR message ILIKE '%' || $2 || '%')
    AND (NOT $3::boolean OR is_fix)
ORDER BY committed_at DESC
LIMIT $4 OFFSET $5
