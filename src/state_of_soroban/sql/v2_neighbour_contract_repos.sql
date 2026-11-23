SELECT
    r.full_name,
    r.stars,
    r.pushed_at,
    r.networks,
    r.language,
    l.link
FROM repo_contract_links AS l
INNER JOIN repos AS r ON l.repo = r.full_name
WHERE l.network = $1 AND l.contract_id = $2 AND l.link IN ('verified', 'deployment', 'code')
ORDER BY r.stars DESC
LIMIT $3
