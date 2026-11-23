WITH topic_repos AS (
    SELECT
        t.topic,
        count(*) AS carriers,
        count(*) FILTER (
            WHERE repos.scanned_at IS NOT NULL OR repos.ecosystem_scanned_at IS NOT NULL
        ) AS evaluated,
        count(*) FILTER (WHERE repos.is_soroban OR repos.is_stellar) AS relevant
    FROM repos
    CROSS JOIN LATERAL unnest(repos.topics) AS t (topic)
    GROUP BY t.topic
)

SELECT
    topic,
    relevant AS repos,
    carriers,
    evaluated,
    relevant::double precision / nullif(evaluated, 0) AS precision
FROM topic_repos
WHERE relevant >= $1
ORDER BY relevant DESC
LIMIT 200
