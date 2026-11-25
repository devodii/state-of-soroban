SELECT
    full_name,
    is_soroban,
    is_fork,
    parent_full_name,
    stars,
    forks,
    language,
    pushed_at,
    window_commits,
    total_commits,
    description,
    owner,
    archived,
    count(*) OVER () AS total
FROM repos
WHERE
    ($1 = '' OR full_name ILIKE '%' || $1 || '%' OR description ILIKE '%' || $1 || '%')
    AND (
        $2 = 'all'
        OR ($2 = 'soroban' AND is_soroban AND NOT is_fork)
        OR ($2 = 'forks' AND is_fork)
        OR ($2 = 'nonfork' AND NOT is_fork)
        OR ($2 = 'extracted' AND scanned_at IS NOT NULL)
    )
ORDER BY
    CASE $5
        WHEN 'stars' THEN stars
        WHEN 'forks' THEN forks
        WHEN 'activity' THEN window_commits
    END DESC NULLS LAST,
    CASE WHEN $5 = 'recent' THEN pushed_at END DESC NULLS LAST,
    CASE WHEN $5 = 'name' THEN full_name END ASC,
    full_name ASC
LIMIT $3 OFFSET $4
