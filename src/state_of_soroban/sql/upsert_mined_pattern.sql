INSERT INTO patterns (id, category, description, matcher, origin, status)
VALUES ($1, 'mined', $2, $3, 'mined', 'active')
ON CONFLICT (id) DO UPDATE SET
    description = excluded.description,
    matcher = excluded.matcher
