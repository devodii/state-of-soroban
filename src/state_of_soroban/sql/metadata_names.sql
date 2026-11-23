WITH generic AS (
    SELECT 'search:topic:' || signature AS tag
    FROM catalog_candidates
    WHERE kind = 'query' AND status = 'rejected'
)

SELECT r.full_name
FROM repos AS r
WHERE $1::boolean OR r.pushed_at IS NULL
ORDER BY
    CASE
        WHEN EXISTS (
            SELECT 1 FROM unnest(r.discovered_via) AS v
            WHERE v NOT LIKE 'search:topic:%'
        ) THEN 0
        WHEN EXISTS (
            SELECT 1 FROM unnest(r.discovered_via) AS v
            WHERE v NOT IN (SELECT tag FROM generic)
        ) THEN 1
        ELSE 2
    END,
    r.full_name
