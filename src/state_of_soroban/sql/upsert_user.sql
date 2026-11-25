INSERT INTO github_users (login, avatar_url, html_url, user_type)
VALUES ($1, $2, $3, $4)
ON CONFLICT (login) DO UPDATE SET
    avatar_url = excluded.avatar_url,
    html_url = excluded.html_url,
    user_type = excluded.user_type,
    seen_at = now()
