WITH q AS (SELECT websearch_to_tsquery('english', $1) AS query)

SELECT
    top.repo,
    top.path AS ref,
    top.relevance,
    top.kind,
    top.path AS title,
    ts_headline(
        'english',
        left(top.text_content, 4000),
        (SELECT query FROM q),
        'MaxWords=38,MinWords=14,MaxFragments=1'
    ) AS snippet,
    'https://github.com/' || top.repo || '/blob/HEAD/' || top.path AS url
FROM (
    SELECT
        d.repo,
        d.path,
        d.kind,
        d.text_content,
        ts_rank_cd(d.search, q.query, 32) AS relevance
    FROM repo_documents AS d
    INNER JOIN repos AS r ON d.repo = r.full_name
    CROSS JOIN q
    WHERE
        d.search @@ q.query
        AND d.kind IN ('readme', 'docs', 'script', 'build', 'ci', 'docker', 'env')
        AND (r.is_stellar OR r.is_soroban)
        AND NOT r.is_fork
    ORDER BY relevance DESC
    LIMIT $2
) AS top
WHERE top.relevance >= $3
