INSERT INTO query_stats (kind, query, hits, new_repos, seconds)
VALUES ($1, $2, $3, $4, $5)
ON CONFLICT (kind, query) DO UPDATE SET
    hits = excluded.hits,
    new_repos = excluded.new_repos,
    seconds = excluded.seconds,
    run_at = now()
