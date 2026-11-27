WITH recent AS (
    SELECT
        c.repo,
        c.author_login,
        c.committed_at
    FROM commits AS c
    INNER JOIN repos AS r ON c.repo = r.full_name AND r.is_soroban AND NOT r.is_fork AND NOT r.archived
    WHERE c.committed_at > now() - make_interval(days => $1)
),

by_author AS (
    SELECT
        repo,
        author_login,
        count(*) AS n
    FROM recent
    GROUP BY repo, author_login
),

top_author AS (
    SELECT
        repo,
        max(n) AS n
    FROM by_author
    GROUP BY repo
),

totals AS (
    SELECT
        repo,
        count(*) AS commits,
        count(DISTINCT author_login) AS authors,
        count(DISTINCT date_trunc('week', committed_at)) AS active_weeks,
        max(committed_at) AS last_commit
    FROM recent
    GROUP BY repo
)

SELECT
    t.repo,
    t.commits,
    t.authors,
    t.active_weeks,
    t.last_commit,
    r.stars,
    r.url,
    coalesce(f.family, t.repo) AS family,
    coalesce(f.members, 1) AS family_members,
    round(a.n::numeric / t.commits, 2)::float AS top_author_share
FROM totals AS t
INNER JOIN top_author AS a ON t.repo = a.repo
INNER JOIN repos AS r ON t.repo = r.full_name
LEFT JOIN repo_families AS f ON t.repo = f.repo
WHERE t.commits >= $2 AND t.authors >= $3
ORDER BY t.commits DESC
