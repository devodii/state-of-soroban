SELECT
    t.id,
    t.name,
    t.url,
    n.relation
FROM need_tools AS n
INNER JOIN tool_catalog AS t ON n.tool = t.id
WHERE n.need = $1
