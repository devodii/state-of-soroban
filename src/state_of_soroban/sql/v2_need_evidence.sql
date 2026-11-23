SELECT
    ranked.kind,
    ranked.repo,
    ranked.ref,
    ranked.relevance,
    ranked.title,
    ranked.url,
    ranked.created_at,
    left(ranked.snippet, 480) AS snippet
FROM (
    SELECT
        e.kind,
        e.repo,
        e.ref,
        e.relevance,
        e.title,
        e.snippet,
        e.url,
        e.created_at,
        row_number() OVER (PARTITION BY e.kind ORDER BY e.relevance DESC) AS rn
    FROM need_evidence AS e
    WHERE e.need = $1
) AS ranked
WHERE ranked.rn <= $2
ORDER BY ranked.kind ASC, ranked.relevance DESC
