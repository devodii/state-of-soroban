SELECT
    f.cluster,
    f.size,
    f.families,
    f.owners,
    f.authors,
    f.commits,
    f.issues,
    f.pulls,
    f.contract_units,
    f.recent_units,
    f.cohesion,
    f.terms,
    f.first_seen,
    f.last_seen,
    count(*) OVER () AS total
FROM frictions AS f
WHERE
    f.run_id = (
        SELECT run_id FROM analysis_runs
        ORDER BY created_at DESC LIMIT 1
    )
    AND f.families >= $1
    AND ($2 = '' OR array_to_string(f.terms, ' ') ILIKE '%' || $2 || '%')
    AND ($3 = 0 OR f.contract_units::float / f.size >= $3)
ORDER BY
    CASE $4 WHEN 'families' THEN f.families END DESC NULLS LAST,
    CASE $4 WHEN 'recent' THEN f.recent_units END DESC NULLS LAST,
    CASE $4 WHEN 'size' THEN f.size END DESC NULLS LAST,
    CASE $4 WHEN 'contract' THEN f.contract_units::float / f.size END DESC NULLS LAST,
    f.families DESC
LIMIT $5 OFFSET $6
