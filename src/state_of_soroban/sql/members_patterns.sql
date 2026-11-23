SELECT DISTINCT
    repo,
    path
FROM pattern_matches
WHERE pattern = ANY($1::text[]) AND NOT in_test
