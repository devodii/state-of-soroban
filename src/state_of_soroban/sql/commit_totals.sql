SELECT
    repo,
    count(*) AS total
FROM commits
GROUP BY repo
