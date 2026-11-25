SELECT
    rc.login,
    rc.contributions,
    u.avatar_url
FROM repo_contributors AS rc
LEFT JOIN github_users AS u ON rc.login = u.login
WHERE rc.repo = $1
ORDER BY rc.contributions DESC
LIMIT 60
