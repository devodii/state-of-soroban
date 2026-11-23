UPDATE repos
SET
    is_stellar = is_stellar OR $2,
    stack = $3,
    stellar_libs = $4,
    ecosystem_scanned_at = now()
WHERE full_name = $1
