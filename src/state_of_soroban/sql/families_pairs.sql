SELECT
    a.repo AS left_repo,
    b.repo AS right_repo,
    count(*) AS shared
FROM commits AS a
INNER JOIN commits AS b ON a.sha = b.sha AND a.repo < b.repo
GROUP BY a.repo, b.repo
HAVING count(*) >= $1
