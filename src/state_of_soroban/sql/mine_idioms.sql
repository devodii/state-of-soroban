WITH base AS (
    SELECT
        r.owner,
        f.repo,
        f.body_hash,
        f.loc,
        f.name,
        f.path,
        f.line_start,
        f.line_end,
        (
            SELECT string_agg(c, ' ' ORDER BY c) FROM unnest(f.calls) AS c
        ) AS signature
    FROM functions AS f
    INNER JOIN repos AS r ON f.repo = r.full_name
    WHERE
        f.is_contract_fn
        AND NOT f.is_test
        AND NOT r.is_fork
        AND f.loc <= 40
        AND cardinality(f.calls) >= 3
        AND (f.calls && $3::text[] OR f.macros && $3::text[])
)

SELECT
    signature,
    count(DISTINCT owner) AS owners,
    count(DISTINCT repo) AS repos,
    count(*) AS occurrences,
    count(DISTINCT body_hash) AS bodies,
    sum(loc) AS loc_total,
    mode() WITHIN GROUP (ORDER BY name) AS common_name,
    (array_agg(repo ORDER BY loc DESC))[1] AS sample_repo,
    (array_agg(path ORDER BY loc DESC))[1] AS sample_path,
    (array_agg(line_start ORDER BY loc DESC))[1] AS sample_start,
    (array_agg(line_end ORDER BY loc DESC))[1] AS sample_end
FROM base
GROUP BY signature
HAVING count(DISTINCT owner) >= $1
ORDER BY count(DISTINCT owner) DESC, count(*) DESC
LIMIT $2
