WITH counts AS (
    SELECT
        repo,
        count(*) AS proposals
    FROM proposal_repos
    GROUP BY repo
)

SELECT
    r.full_name,
    r.stars,
    r.language,
    r.description,
    r.networks,
    r.pushed_at,
    r.rust_loc,
    r.window_commits,
    r.is_soroban,
    r.is_stellar,
    r.topics[1:6] AS topics,
    coalesce(c.proposals, 0) AS proposals
FROM repos AS r
LEFT JOIN counts AS c ON r.full_name = c.repo
WHERE r.is_soroban OR r.is_stellar
