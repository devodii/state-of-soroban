SELECT
    (
        SELECT count(*) FROM commits
        WHERE is_fix
    ) + (SELECT count(*) FROM issues
    ) AS total
