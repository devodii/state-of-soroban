SELECT
    count(*) AS hits,
    count(*) FILTER (WHERE cardinality(discovered_via) = 1) AS exclusive
FROM repos
WHERE $1 = any(discovered_via)
