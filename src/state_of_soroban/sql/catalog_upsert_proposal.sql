INSERT INTO proposals (
    id, name, kind, summary, sketch, min_repos, min_share, min_occurrences,
    covered_by
)
VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
ON CONFLICT (id) DO UPDATE SET
    name = excluded.name,
    kind = excluded.kind,
    summary = excluded.summary,
    sketch = excluded.sketch,
    min_repos = excluded.min_repos,
    min_share = excluded.min_share,
    min_occurrences = excluded.min_occurrences,
    covered_by = excluded.covered_by
