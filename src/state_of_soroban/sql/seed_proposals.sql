SELECT
    id,
    covered_by,
    min_repos,
    min_share,
    min_occurrences
FROM proposals
WHERE origin = 'seed'
