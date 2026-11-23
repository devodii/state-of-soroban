SELECT
    kind,
    query,
    hits,
    new_repos,
    soroban_repos,
    seconds
FROM query_stats
ORDER BY hits DESC
