SELECT
    (SELECT count(*) FROM repos) AS repos,
    (
        SELECT count(*) FROM repos
        WHERE is_soroban
    ) AS soroban_repos,
    (
        SELECT count(*) FROM repos
        WHERE cloned_at IS NOT NULL
    ) AS cloned,
    (
        SELECT count(*) FROM repos
        WHERE pushed_at IS NOT NULL
    ) AS with_metadata,
    (
        SELECT greatest(reltuples, 0)::bigint FROM pg_class
        WHERE oid = 'functions'::regclass
    ) AS functions,
    (
        SELECT greatest(reltuples, 0)::bigint FROM pg_class
        WHERE oid = 'pattern_matches'::regclass
    ) AS pattern_matches,
    (
        SELECT greatest(reltuples, 0)::bigint FROM pg_class
        WHERE oid = 'commits'::regclass
    ) AS commits,
    (
        SELECT count(*) FROM commits
        WHERE is_fix
    ) AS fix_commits,
    (
        SELECT greatest(reltuples, 0)::bigint FROM pg_class
        WHERE oid = 'issues'::regclass
    ) AS issues,
    (SELECT count(*) FROM deployed_contracts) AS contracts,
    (SELECT count(*) FROM wasm_modules) AS wasm_modules,
    (
        SELECT count(*) FROM catalog_candidates
        WHERE status = 'open'
    ) AS open_candidates
