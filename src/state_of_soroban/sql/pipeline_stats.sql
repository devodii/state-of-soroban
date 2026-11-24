SELECT
    (SELECT count(*) FROM repos) AS discovered,
    (
        SELECT count(*) FROM checkpoints
        WHERE job = 'metadata' AND status = 'done'
    ) AS metadata,
    (
        SELECT count(*) FROM checkpoints
        WHERE job = 'extract' AND status = 'done'
    ) AS extracted,
    (
        SELECT count(*) FROM checkpoints
        WHERE job = 'extract' AND status IN ('failed', 'gone')
    ) AS extract_failed,
    (
        SELECT count(*) FROM checkpoints
        WHERE job = 'history' AND status = 'done'
    ) AS history,
    (SELECT count(*) FROM commits) AS commits,
    (SELECT count(*) FROM issues) AS issues,
    (SELECT count(*) FROM source_files) AS source_files;
