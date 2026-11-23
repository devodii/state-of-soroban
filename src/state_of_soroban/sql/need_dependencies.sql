SELECT
    d.repo,
    d.name AS ref,
    1.0 AS relevance,
    d.requirement AS snippet,
    d.ecosystem || ':' || d.name AS title,
    'https://github.com/' || d.repo AS url
FROM ecosystem_dependencies AS d
INNER JOIN repos AS r ON d.repo = r.full_name
WHERE lower(d.name) = any($1::text[]) AND NOT r.is_fork
ORDER BY r.stars DESC
LIMIT $2
