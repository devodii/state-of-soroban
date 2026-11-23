SELECT
    e.need AS id,
    n.title,
    count(*) AS evidence,
    max(e.relevance) AS relevance
FROM need_evidence AS e
INNER JOIN tooling_needs AS n ON e.need = n.id
WHERE e.repo = $1
GROUP BY e.need, n.title
ORDER BY max(e.relevance) DESC
LIMIT 12
