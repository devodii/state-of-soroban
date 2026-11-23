SELECT
    count(DISTINCT r.owner) AS owners,
    count(DISTINCT m.repo) AS repos,
    count(*) AS occurrences,
    count(DISTINCT m.shape_hash) AS bodies,
    coalesce(sum(m.line_end - m.line_start + 1), 0) AS loc_total
FROM pattern_matches AS m
INNER JOIN repos AS r ON m.repo = r.full_name
WHERE m.pattern = any($1::text[]) AND NOT m.in_test AND NOT r.is_fork
