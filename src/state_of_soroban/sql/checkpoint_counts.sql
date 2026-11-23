SELECT
    job,
    status,
    count(*) AS units
FROM checkpoints
GROUP BY job, status
ORDER BY job ASC, status ASC
