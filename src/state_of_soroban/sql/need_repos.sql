SELECT
    r.full_name AS repo,
    r.full_name AS ref,
    r.description AS snippet,
    r.url,
    ts_rank_cd(r.search, websearch_to_tsquery('english', $1), 32) AS relevance,
    coalesce(r.description, r.full_name) AS title
FROM repos AS r
WHERE
    r.search @@ websearch_to_tsquery('english', $1)
    AND (r.is_stellar OR r.is_soroban)
    AND NOT r.is_fork
ORDER BY relevance DESC, r.stars DESC
LIMIT $2
