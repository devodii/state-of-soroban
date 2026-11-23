SELECT
    d.repo,
    d.path AS ref,
    1.0 AS relevance,
    d.path AS title,
    left(d.text_content, 300) AS snippet,
    'https://github.com/' || d.repo || '/blob/HEAD/' || d.path AS url
FROM repo_documents AS d
INNER JOIN repos AS r ON d.repo = r.full_name
WHERE d.path ~* $1 AND (r.is_stellar OR r.is_soroban) AND NOT r.is_fork
ORDER BY r.stars DESC
LIMIT $2
