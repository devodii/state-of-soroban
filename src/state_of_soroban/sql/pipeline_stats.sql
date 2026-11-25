SELECT
    (SELECT count(*) FROM repos) AS discovered,
    (
        SELECT count(*) FROM repos
        WHERE is_soroban
    ) AS soroban,
    (
        SELECT count(*) FROM repos
        WHERE scanned_at IS NOT NULL
    ) AS extracted,
    (
        SELECT count(*) FROM checkpoints
        WHERE job = 'history' AND status = 'done'
    ) AS history,
    (SELECT count(*) FROM commits) AS commits,
    (SELECT count(*) FROM issues) AS issues,
    (SELECT count(*) FROM source_files) AS source_files;
