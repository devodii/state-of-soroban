INSERT INTO tooling_needs (id, title, category, summary, origin, query, signals)
VALUES ($1, $2, 'mined', $3, 'mined', $4, '{}')
ON CONFLICT (id) DO UPDATE SET
    title = excluded.title,
    summary = excluded.summary,
    query = excluded.query
