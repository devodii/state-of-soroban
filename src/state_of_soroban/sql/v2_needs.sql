SELECT
    n.id,
    n.title,
    n.category,
    n.origin,
    n.status,
    n.score,
    n.summary,
    coalesce((n.demand ->> 'pain_issues')::int, 0) AS pain_issues,
    coalesce((n.demand ->> 'pain_owners')::int, 0) AS pain_owners,
    coalesce((n.demand ->> 'issues')::int, 0) AS issues,
    coalesce((n.demand ->> 'repos')::int, 0) AS repos,
    coalesce((n.demand ->> 'owners')::int, 0) AS owners,
    coalesce((n.demand ->> 'open_issues')::int, 0) AS open_issues,
    coalesce((n.demand ->> 'custom_repos')::int, 0) AS custom_repos,
    coalesce((n.demand ->> 'questions')::int, 0) AS questions,
    n.evidence -> 'components' AS components,
    n.rfp ->> 'priority' AS priority,
    (
        SELECT count(*) FROM comments AS c
        WHERE c.target_kind = 'need' AND c.target_id = n.id
    ) AS comments,
    (
        SELECT array_agg(t.name ORDER BY t.name)
        FROM need_tools AS nt
        INNER JOIN tool_catalog AS t ON nt.tool = t.id
        WHERE nt.need = n.id
    ) AS tools
FROM tooling_needs AS n
ORDER BY n.score DESC
LIMIT $1
