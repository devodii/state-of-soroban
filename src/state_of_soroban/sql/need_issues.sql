WITH q AS (SELECT websearch_to_tsquery('english', $1) AS query)

SELECT
    top.repo,
    top.number::text AS ref,
    top.relevance,
    top.title,
    top.url,
    top.created_at,
    top.kind,
    top.state,
    top.comments,
    top.reactions,
    ts_headline(
        'english',
        coalesce(left(top.body, 3000), top.title),
        (SELECT query FROM q),
        'MaxWords=38,MinWords=14,MaxFragments=1'
    ) AS snippet
FROM (
    SELECT
        i.repo,
        i.number,
        i.title,
        i.body,
        i.url,
        i.created_at,
        i.kind,
        i.state,
        i.comments,
        i.reactions,
        ts_rank_cd(i.search, q.query, 32) AS relevance
    FROM issues AS i
    INNER JOIN repos AS r ON i.repo = r.full_name
    CROSS JOIN q
    WHERE i.search @@ q.query AND (r.is_stellar OR r.is_soroban) AND NOT r.is_fork
    ORDER BY relevance DESC
    LIMIT $2
) AS top
WHERE top.relevance >= $3
