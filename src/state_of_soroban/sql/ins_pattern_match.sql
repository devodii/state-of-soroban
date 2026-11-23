INSERT INTO pattern_matches (
    repo, path, pattern, start_byte, line_start, line_end, fn_name, in_test,
    snippet, shape_hash, captures
)
VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
ON CONFLICT (repo, path, pattern, start_byte) DO NOTHING
