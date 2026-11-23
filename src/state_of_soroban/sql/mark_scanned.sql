UPDATE repos
SET
    is_soroban = $2,
    networks = $3,
    locked_versions = $4,
    rust_files = $5,
    rust_loc = $6,
    contract_crates = $7,
    cloned_at = now(),
    scanned_at = now()
WHERE full_name = $1
