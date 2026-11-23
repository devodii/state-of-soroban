SELECT
    count(DISTINCT owner) AS owners,
    count(*) AS repos
FROM repos
WHERE (is_stellar OR is_soroban) AND NOT is_fork
