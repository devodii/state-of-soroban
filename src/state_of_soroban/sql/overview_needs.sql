SELECT
    id,
    title,
    category,
    origin,
    status,
    score,
    summary,
    demand,
    evidence,
    rfp,
    scored_at,
    (
        SELECT count(*) FROM comments AS c
        WHERE c.target_kind = 'need' AND c.target_id = tooling_needs.id
    ) AS comments,
    (
        SELECT string_agg(t.name, ', ')
        FROM need_tools AS n
        INNER JOIN tool_catalog AS t ON n.tool = t.id
        WHERE n.need = tooling_needs.id
    ) AS tools
FROM tooling_needs
ORDER BY score DESC
LIMIT 300
