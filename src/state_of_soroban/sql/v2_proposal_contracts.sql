WITH top_repos AS (
    SELECT pr.repo
    FROM proposal_repos AS pr
    WHERE pr.proposal = $1
    ORDER BY pr.weight DESC
    LIMIT 80
)

SELECT DISTINCT ON (l.network, l.contract_id)
    l.network,
    l.contract_id,
    l.live,
    l.link,
    l.repo
FROM repo_contract_links AS l
INNER JOIN top_repos AS t ON l.repo = t.repo
WHERE l.link IN ('verified', 'deployment', 'code')
ORDER BY l.network ASC, l.contract_id ASC, l.live DESC
LIMIT $2
