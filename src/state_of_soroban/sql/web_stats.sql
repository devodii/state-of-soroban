SELECT
    (SELECT count(*) FROM repos) AS repos,
    (
        SELECT count(*) FROM repos
        WHERE is_soroban
    ) AS soroban,
    (
        SELECT count(*) FROM repos
        WHERE is_fork
    ) AS forks,
    (
        SELECT count(*) FROM repos
        WHERE scanned_at IS NOT NULL
    ) AS extracted,
    (SELECT count(*) FROM commits) AS commits,
    (
        SELECT count(*) FROM commits
        WHERE is_fix
    ) AS fix_commits,
    (SELECT count(*) FROM issues) AS issues,
    (SELECT count(*) FROM functions) AS functions,
    (SELECT count(*) FROM github_users) AS users
