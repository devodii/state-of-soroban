(
    SELECT
        'proposal' AS kind,
        id,
        name AS label,
        left(summary, 110) AS sub,
        score::float AS score
    FROM proposals
    WHERE name ILIKE $1 OR id ILIKE $1
    ORDER BY score DESC
    LIMIT 6
)
UNION ALL
(
    SELECT
        'need' AS kind,
        id,
        title AS label,
        category AS sub,
        score::float AS score
    FROM tooling_needs
    WHERE title ILIKE $1 OR id ILIKE $1
    ORDER BY score DESC
    LIMIT 6
)
UNION ALL
(
    SELECT
        'tool' AS kind,
        id,
        name AS label,
        left(description, 110) AS sub,
        0::float AS score
    FROM tool_catalog
    WHERE name ILIKE $1 OR id ILIKE $1
    ORDER BY name ASC
    LIMIT 4
)
