SELECT
    id,
    kind,
    title,
    repos,
    occurrences,
    score,
    status,
    suggestion
FROM catalog_candidates
ORDER BY score DESC
LIMIT 200
