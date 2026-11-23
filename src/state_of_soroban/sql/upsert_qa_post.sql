INSERT INTO qa_posts (source, id, title, body, tags, score, views, answers, answered, created_at, url)
VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
ON CONFLICT (source, id) DO UPDATE SET
    title = excluded.title,
    body = excluded.body,
    tags = excluded.tags,
    score = excluded.score,
    views = excluded.views,
    answers = excluded.answers,
    answered = excluded.answered
