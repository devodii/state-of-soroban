SELECT
    lower(f.name) AS name,
    count(DISTINCT r.owner) AS owners,
    count(DISTINCT f.repo) AS repos,
    count(*) AS occurrences,
    count(DISTINCT f.body_hash) AS bodies,
    count(DISTINCT f.shape_hash) AS shapes,
    sum(f.loc) AS loc_total,
    (array_agg(f.repo ORDER BY f.loc DESC))[1] AS sample_repo,
    (array_agg(f.path ORDER BY f.loc DESC))[1] AS sample_path,
    (array_agg(f.line_start ORDER BY f.loc DESC))[1] AS sample_start,
    (array_agg(f.line_end ORDER BY f.loc DESC))[1] AS sample_end
FROM functions AS f
INNER JOIN repos AS r ON f.repo = r.full_name
WHERE
    NOT f.is_test
    AND NOT r.is_fork
    AND f.loc <= 30
    AND f.name !~ '^(new|default|from|fmt|eq|hash|clone|drop|test|main)$'
    AND f.is_contract_fn = FALSE
    AND length(f.name) > 3
    AND (f.calls && $3::text[] OR f.macros && $3::text[] OR f.params::text ~ 'Env')
GROUP BY lower(f.name)
HAVING count(DISTINCT r.owner) >= $1
ORDER BY count(DISTINCT r.owner) DESC, count(*) DESC
LIMIT $2
