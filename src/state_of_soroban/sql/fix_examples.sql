WITH members AS (
    SELECT DISTINCT
        m.repo,
        m.path
    FROM unnest($1::text[], $2::text[]) AS m (repo, path)
)

SELECT DISTINCT ON (c.repo, c.sha)
    c.repo,
    c.sha,
    c.committed_at,
    split_part(c.message, E'\n', 1) AS message
FROM commit_files AS cf
INNER JOIN commits AS c ON cf.repo = c.repo AND cf.sha = c.sha
INNER JOIN members AS mm ON cf.repo = mm.repo AND cf.path = mm.path
WHERE
    c.is_fix
    AND c.touches_rust
    AND c.message !~* '(typo|\mci\M|lint|format|readme|\mdocs?\M|workflow|dependabot|\mbump\M|changelog)'
ORDER BY c.repo ASC, c.sha ASC, c.committed_at DESC
LIMIT 4
