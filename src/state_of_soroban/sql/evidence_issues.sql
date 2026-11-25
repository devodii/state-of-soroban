INSERT INTO evidence (
    kind, repo, ref, family, owner, author_login, occurred_at, title, body, url,
    is_bot, dup_key
)
SELECT
    i.kind,
    i.repo,
    i.number::text,
    coalesce(f.family, i.repo),
    r.owner,
    i.author_login,
    i.created_at,
    i.title,
    left(i.body, 800),
    i.url,
    coalesce(i.author_login ~* '(\[bot\]|dependabot|renovate|github-actions)$', false),
    md5(lower(regexp_replace(i.title, '[^a-zA-Z ]', '', 'g')))
FROM issues AS i
INNER JOIN repos AS r ON i.repo = r.full_name
LEFT JOIN repo_families AS f ON i.repo = f.repo
WHERE r.is_soroban AND NOT r.is_fork AND (i.kind = 'issue' OR i.is_bug)
