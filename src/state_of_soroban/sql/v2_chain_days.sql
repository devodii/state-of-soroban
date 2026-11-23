SELECT
    network,
    day,
    ledgers,
    transactions,
    failed_transactions,
    operations,
    contract_calls,
    contracts_called
FROM network_days
ORDER BY day ASC, network ASC
