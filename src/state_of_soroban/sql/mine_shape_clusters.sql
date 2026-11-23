WITH base AS (
    SELECT
        f.shape_hash,
        f.repo,
        r.owner,
        f.body_hash,
        f.loc,
        f.name,
        f.path,
        f.line_start,
        f.line_end,
        f.is_contract_fn,
        EXISTS(
            SELECT 1 FROM pattern_matches AS m
            WHERE m.repo = f.repo AND m.path = f.path AND m.fn_name = f.name AND NOT m.in_test
        ) AS covered
    FROM functions AS f
    INNER JOIN repos AS r ON f.repo = r.full_name
    WHERE
        NOT f.is_test
        AND NOT r.is_fork
        AND f.shape_nodes >= $1
        AND f.loc <= $2
        AND (f.calls && $5::text[] OR f.macros && $5::text[] OR f.params::text ~ 'Env')
)

SELECT
    shape_hash,
    COUNT(DISTINCT owner) AS owners,
    COUNT(DISTINCT repo) AS repos,
    COUNT(*) AS occurrences,
    COUNT(DISTINCT body_hash) AS bodies,
    SUM(loc) AS loc_total,
    COUNT(*) FILTER (WHERE covered) AS covered_count,
    COUNT(*) FILTER (WHERE is_contract_fn) AS contract_fns,
    MODE() WITHIN GROUP (ORDER BY name) AS common_name,
    (ARRAY_AGG(repo ORDER BY loc DESC))[1] AS sample_repo,
    (ARRAY_AGG(path ORDER BY loc DESC))[1] AS sample_path,
    (ARRAY_AGG(line_start ORDER BY loc DESC))[1] AS sample_start,
    (ARRAY_AGG(line_end ORDER BY loc DESC))[1] AS sample_end
FROM base
GROUP BY shape_hash
HAVING COUNT(DISTINCT owner) >= $3
ORDER BY COUNT(DISTINCT owner) DESC, COUNT(*) DESC
LIMIT $4
