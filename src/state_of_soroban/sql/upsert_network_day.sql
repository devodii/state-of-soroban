INSERT INTO network_days (
    network, day, ledgers, transactions, failed_transactions, operations,
    contract_calls, contracts_called
)
VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
ON CONFLICT (network, day) DO UPDATE SET
    ledgers = excluded.ledgers,
    transactions = excluded.transactions,
    failed_transactions = excluded.failed_transactions,
    operations = excluded.operations,
    contract_calls = excluded.contract_calls,
    contracts_called = excluded.contracts_called
