INSERT INTO patterns (id, category, description, matcher)
VALUES ($1, $2, $3, $4)
ON CONFLICT (id) DO UPDATE SET
    category = excluded.category,
    description = excluded.description,
    matcher = excluded.matcher
