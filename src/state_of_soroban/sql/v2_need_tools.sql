SELECT
    t.id,
    t.name,
    t.category,
    t.url,
    t.description,
    nt.relation,
    nt.relevance
FROM need_tools AS nt
INNER JOIN tool_catalog AS t ON nt.tool = t.id
WHERE nt.need = $1
ORDER BY nt.relevance DESC, t.name ASC
