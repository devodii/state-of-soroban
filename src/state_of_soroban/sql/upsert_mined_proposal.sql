INSERT INTO proposals (
    id, name, kind, summary, sketch, min_repos, min_share, min_occurrences,
    origin, status, score, evidence, scored_at
)
VALUES ($1, $2, $3, $4, $5, $6, $7, $8, 'mined', 'proposed', $9, $10, now())
ON CONFLICT (id) DO UPDATE SET
    name = excluded.name,
    summary = excluded.summary,
    sketch = excluded.sketch,
    score = excluded.score,
    evidence = excluded.evidence,
    scored_at = now()
