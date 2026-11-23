INSERT INTO comments (target_kind, target_id, author, body)
VALUES ($1, $2, $3, $4)
RETURNING id, author, body, created_at
