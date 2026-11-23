INSERT INTO tooling_needs (id, title, category, summary, origin, query, signals, rfp)
VALUES ($1, $2, $3, $4, 'seed', $5, $6, $7)
ON CONFLICT (id) DO UPDATE SET
    title = excluded.title,
    category = excluded.category,
    summary = excluded.summary,
    query = excluded.query,
    signals = excluded.signals
