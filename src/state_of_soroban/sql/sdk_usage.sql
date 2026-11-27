WITH used AS (
    SELECT DISTINCT
        f.repo,
        c AS name
    FROM functions AS f
    INNER JOIN repos AS r ON f.repo = r.full_name AND r.is_soroban AND NOT r.is_fork
    CROSS JOIN LATERAL unnest(f.calls) AS c
    WHERE c = any($1)
),

defined AS (
    SELECT DISTINCT
        repo,
        name
    FROM functions
    WHERE name = any($1)
)

SELECT
    u.name,
    count(*) AS repos,
    count(d.repo) AS defining_repos,
    (array_agg(u.repo ORDER BY r.stars DESC) FILTER (WHERE d.repo IS NULL))[1:3] AS example_repos
FROM used AS u
INNER JOIN repos AS r ON u.repo = r.full_name
LEFT JOIN defined AS d ON u.repo = d.repo AND u.name = d.name
GROUP BY u.name
