SELECT
    l.network,
    l.contract_id,
    l.live,
    l.link
FROM repo_contract_links AS l
WHERE l.repo = $1 AND l.link IN ('verified', 'deployment', 'code')
ORDER BY
    CASE l.link WHEN 'verified' THEN 1 WHEN 'deployment' THEN 2 ELSE 3 END ASC,
    l.live DESC
LIMIT $2
