SELECT
    count(DISTINCT r.owner) AS owners,
    count(DISTINCT e.repo) AS repos,
    count(*) FILTER (WHERE e.kind IN ('issue', 'pull')) AS issues,
    count(*) FILTER (WHERE e.kind = 'document') AS documents,
    count(DISTINCT e.repo) FILTER (WHERE e.kind IN ('dependency', 'path')) AS custom_repos,
    count(*) FILTER (WHERE e.kind IN ('issue', 'pull') AND r.owner = any($2::text[])) AS official,
    coalesce(avg(e.relevance) FILTER (WHERE e.kind IN ('issue', 'pull', 'document')), 0) AS avg_relevance,
    count(*) FILTER (WHERE e.created_at >= now() - make_interval(days => $3)) AS recent,
    count(*) FILTER (WHERE e.created_at IS NOT NULL) AS dated,
    coalesce(sum(i.reactions + i.comments), 0) AS engagement,
    count(*) FILTER (WHERE i.state = 'open') AS open_issues
FROM need_evidence AS e
INNER JOIN repos AS r ON e.repo = r.full_name
LEFT JOIN issues AS i ON e.kind IN ('issue', 'pull') AND e.repo = i.repo AND e.ref = i.number::text
WHERE e.need = $1
