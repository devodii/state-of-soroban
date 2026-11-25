UPDATE frictions AS f
SET
    families = s.families,
    owners = s.owners,
    authors = s.authors,
    commits = s.commits,
    issues = s.issues,
    pulls = s.pulls,
    contract_units = s.contract_units,
    recent_units = s.recent_units,
    first_seen = s.first_seen,
    last_seen = s.last_seen
FROM (
    SELECT
        m.cluster,
        count(DISTINCT e.family) AS families,
        count(DISTINCT e.owner) AS owners,
        count(DISTINCT e.author_login) AS authors,
        count(*) FILTER (WHERE e.kind = 'commit') AS commits,
        count(*) FILTER (WHERE e.kind = 'issue') AS issues,
        count(*) FILTER (WHERE e.kind = 'pull') AS pulls,
        count(*) FILTER (WHERE 'contract' = any(e.layers)) AS contract_units,
        count(*) FILTER (WHERE e.occurred_at > now() - interval '90 days') AS recent_units,
        min(e.occurred_at) AS first_seen,
        max(e.occurred_at) AS last_seen
    FROM friction_members AS m
    INNER JOIN evidence AS e ON m.kind = e.kind AND m.repo = e.repo AND m.ref = e.ref
    WHERE m.run_id = $1
    GROUP BY m.cluster
) AS s
WHERE f.run_id = $1 AND f.cluster = s.cluster
