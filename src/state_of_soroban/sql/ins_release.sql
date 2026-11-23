INSERT INTO releases (repo, tag, name, body, prerelease, published_at)
VALUES ($1, $2, $3, $4, $5, $6)
ON CONFLICT (repo, tag) DO UPDATE SET
    name = excluded.name,
    body = excluded.body,
    prerelease = excluded.prerelease,
    published_at = excluded.published_at
