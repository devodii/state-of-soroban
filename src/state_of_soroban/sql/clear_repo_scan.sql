WITH c1 AS (
    DELETE FROM source_files
    WHERE repo = $1
),

c2 AS (
    DELETE FROM crates
    WHERE repo = $1
),

c3 AS (
    DELETE FROM repo_documents
    WHERE repo = $1
),

c4 AS (
    DELETE FROM repo_network_signals
    WHERE repo = $1
),

c5 AS (
    DELETE FROM repo_contract_refs
    WHERE repo = $1
),

c6 AS (
    DELETE FROM commits
    WHERE repo = $1
)

DELETE FROM repo_contributors
WHERE repo = $1
