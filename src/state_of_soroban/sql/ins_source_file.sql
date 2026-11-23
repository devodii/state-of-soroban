INSERT INTO source_files (
    repo, path, crate_path, blob_sha, size, loc, is_test, parse_errors, content,
    analysed_with, uses, macros
)
VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
ON CONFLICT (repo, path) DO NOTHING
