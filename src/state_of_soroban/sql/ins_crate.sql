INSERT INTO crates (
    repo, path, name, version, edition, is_workspace_root, workspace_members,
    is_contract, crate_types, soroban_sdk_requirement, soroban_sdk_resolved,
    features, profiles, metadata
)
VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
ON CONFLICT (repo, path) DO NOTHING
