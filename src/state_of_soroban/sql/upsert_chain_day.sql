INSERT INTO chain_days (network, day, status, ledgers, invocations, finished_at)
VALUES ($1, $2, 'done', $3, $4, now())
ON CONFLICT (network, day) DO UPDATE SET
    status = 'done',
    ledgers = excluded.ledgers,
    invocations = excluded.invocations,
    finished_at = now()
