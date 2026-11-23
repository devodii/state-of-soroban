INSERT INTO type_defs (
    repo, path, line_start, name, kind, attributes, derives, is_contracttype,
    is_contracterror, is_contractevent, members, shape_hash
)
VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
ON CONFLICT (repo, path, line_start, name) DO NOTHING
