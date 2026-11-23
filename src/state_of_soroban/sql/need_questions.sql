WITH q AS (SELECT websearch_to_tsquery('english', $1) AS query)

SELECT
    top.source AS repo,
    top.id::text AS ref,
    top.relevance,
    top.title,
    top.url,
    top.created_at,
    ts_headline('english', coalesce(left(top.body, 3000), top.title), (SELECT query FROM q), 'MaxWords=38,MinWords=14,MaxFragments=1') AS snippet
FROM (
    SELECT
        p.source,
        p.id,
        p.title,
        p.body,
        p.url,
        p.created_at,
        ts_rank_cd(p.search, q.query, 32) AS relevance
    FROM qa_posts AS p
    CROSS JOIN q
    WHERE p.search @@ q.query
    ORDER BY relevance DESC
    LIMIT $2
) AS top
WHERE top.relevance >= $3
