INSERT INTO functions (
    repo, path, line_start, name, line_end, loc, impl_type, trait_name, visibility,
    attributes, params, return_type, is_contract_fn, is_test, body_hash, shape_hash,
    shape_nodes, calls, macros
)
VALUES (
    $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17,
    $18, $19
)
ON CONFLICT (repo, path, line_start, name) DO NOTHING
