SELECT count(DISTINCT f.repo) AS repos
FROM functions AS f
INNER JOIN repos AS r ON f.repo = r.full_name AND r.is_soroban AND NOT r.is_fork
