SELECT
    (
        SELECT count(*) FROM repos
        WHERE is_soroban
    ) AS soroban_repos,
    (
        SELECT count(*) FROM repos
        WHERE is_stellar AND NOT is_soroban
    ) AS stellar_repos,
    (
        SELECT count(*) FROM repos
        WHERE is_soroban AND 'mainnet' = any(networks)
    ) AS mainnet_repos,
    (
        SELECT count(*) FROM repos
        WHERE is_soroban AND 'testnet' = any(networks)
    ) AS testnet_repos,
    (SELECT count(*) FROM proposals) AS proposals,
    (SELECT count(*) FROM tooling_needs) AS needs,
    (SELECT count(*) FROM patterns) AS patterns,
    (
        SELECT count(*) FROM deployed_contracts
        WHERE network = 'mainnet'
    ) AS mainnet_contracts,
    (
        SELECT count(*) FROM deployed_contracts
        WHERE network = 'testnet'
    ) AS testnet_contracts,
    (
        SELECT count(*) FROM deployed_contracts
        WHERE live
    ) AS live_contracts,
    (
        SELECT greatest(reltuples, 0)::bigint FROM pg_class
        WHERE oid = 'functions'::regclass
    ) AS functions,
    (
        SELECT greatest(reltuples, 0)::bigint FROM pg_class
        WHERE oid = 'commits'::regclass
    ) AS commits,
    (
        SELECT greatest(reltuples, 0)::bigint FROM pg_class
        WHERE oid = 'issues'::regclass
    ) AS issues,
    (SELECT count(*) FROM comments) AS comments,
    (SELECT max(day) FROM network_days) AS last_day,
    (SELECT min(day) FROM network_days) AS first_day
