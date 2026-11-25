INSERT INTO evidence (
    kind, repo, ref, family, owner, author_login, occurred_at, title, body, url,
    layers, files, is_bot, dup_key
)
WITH layered AS (
    SELECT
        cf.repo,
        cf.sha,
        count(*) AS files,
        array_agg(
            DISTINCT
            CASE
                WHEN cf.path ~ '\.rs$' AND EXISTS (
                    SELECT 1 FROM crates AS cr
                    WHERE
                        cr.repo = cf.repo AND cr.is_contract
                        AND (cr.path = '.' OR cf.path LIKE cr.path || '/%')
                ) THEN 'contract'
                WHEN cf.path ~ '\.rs$' THEN 'rust'
                WHEN cf.path ~ '(^|/)(Cargo\.toml|package\.json|go\.mod|pyproject\.toml)$' THEN 'manifest'
                WHEN cf.path ~ '\.(ts|tsx|js|jsx|mjs|vue|svelte)$' THEN 'web'
                WHEN cf.path ~ '\.(py|go|java|kt|swift|rb|php|cs)$' THEN 'app'
                WHEN cf.path ~ '(^|/)\.github/|\.ya?ml$|Dockerfile|Makefile' THEN 'infra'
                WHEN cf.path ~ '\.(md|mdx|rst|txt)$' THEN 'docs'
                ELSE 'other'
            END
        ) AS layers
    FROM commit_files AS cf
    GROUP BY cf.repo, cf.sha
),

canonical AS (
    SELECT DISTINCT ON (c.sha)
        c.*,
        coalesce(f.family, c.repo) AS family,
        r.owner
    FROM commits AS c
    INNER JOIN repos AS r ON c.repo = r.full_name
    LEFT JOIN repo_families AS f ON c.repo = f.repo
    WHERE c.is_fix AND c.parents <= 1 AND r.is_soroban AND NOT r.is_fork
    ORDER BY c.sha ASC, r.stars DESC NULLS LAST, c.repo ASC
)

SELECT
    'commit',
    k.repo,
    k.sha,
    k.family,
    k.owner,
    k.author_login,
    k.committed_at,
    split_part(k.message, E'\n', 1),
    left(substr(k.message, length(split_part(k.message, E'\n', 1)) + 1), 800),
    'https://github.com/' || k.repo || '/commit/' || k.sha,
    coalesce(l.layers, '{}'),
    coalesce(l.files, 0),
    coalesce(k.author_login ~* '(\[bot\]|dependabot|renovate|github-actions)$', FALSE),
    md5(lower(regexp_replace(split_part(k.message, E'\n', 1), '[^a-zA-Z ]', '', 'g')))
FROM canonical AS k
LEFT JOIN layered AS l ON k.repo = l.repo AND k.sha = l.sha
