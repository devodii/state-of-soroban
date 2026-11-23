SELECT
    count(DISTINCT owner) AS total_owners,
    count(*) AS total_repos
FROM repos
WHERE is_soroban AND NOT is_fork
