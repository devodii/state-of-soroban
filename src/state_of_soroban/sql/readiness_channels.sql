WITH confirmed AS (
    SELECT
        r.discovered_at,
        EXISTS(
            SELECT 1 FROM UNNEST(r.discovered_via) AS v
            WHERE v LIKE 'code:%'
        ) AS by_code,
        EXISTS(
            SELECT 1 FROM UNNEST(r.discovered_via) AS v
            WHERE v LIKE 'search:%'
        ) AS by_search,
        EXISTS(
            SELECT 1 FROM UNNEST(r.discovered_via) AS v
            WHERE v LIKE 'dependents:%' OR v LIKE 'crates.io:%'
        ) AS by_graph
    FROM repos AS r
    WHERE r.is_soroban
)

SELECT
    COUNT(*) AS confirmed,
    COUNT(*) FILTER (WHERE by_code) AS code,
    COUNT(*) FILTER (WHERE by_search) AS search,
    COUNT(*) FILTER (WHERE by_graph) AS graph,
    COUNT(*) FILTER (WHERE by_code AND by_search) AS code_search,
    COUNT(*) FILTER (WHERE by_code AND by_graph) AS code_graph,
    COUNT(*) FILTER (WHERE by_search AND by_graph) AS search_graph,
    COUNT(*) FILTER (
        WHERE discovered_at > NOW() - MAKE_INTERVAL(hours => $1::int)
    ) AS recent,
    COALESCE(
        EXTRACT(EPOCH FROM NOW() - (SELECT MIN(r.discovered_at) FROM repos AS r)) / 3600,
        0
    ) AS running_hours
FROM confirmed
