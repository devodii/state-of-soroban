SELECT
    rc.login,
    u.avatar_url,
    count(*) AS repos,
    sum(rc.contributions) AS contributions
FROM repo_contributors AS rc
LEFT JOIN github_users AS u ON rc.login = u.login
WHERE $1 = '' OR rc.login ILIKE '%' || $1 || '%'
GROUP BY rc.login, u.avatar_url
ORDER BY repos DESC, contributions DESC
LIMIT $2 OFFSET $3
