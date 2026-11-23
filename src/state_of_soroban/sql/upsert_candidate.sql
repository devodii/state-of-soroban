INSERT INTO catalog_candidates (
    id, kind, title, signature, repos, occurrences, score, evidence, suggestion
)
VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
ON CONFLICT (id) DO UPDATE SET
    title = excluded.title,
    repos = excluded.repos,
    occurrences = excluded.occurrences,
    score = excluded.score,
    evidence = excluded.evidence,
    suggestion = excluded.suggestion,
    last_seen_at = now()
