SELECT
    a.network,
    a.contract_id,
    sum(a.invocations) AS invocations,
    sum(a.successful) AS successful,
    max(a.callers) AS peak_daily_callers,
    count(*) AS active_days,
    min(a.day) AS first_day,
    max(a.day) AS last_day,
    (
        SELECT string_agg(DISTINCT rc.repo, ', ')
        FROM repo_contract_refs AS rc
        WHERE rc.contract_id = a.contract_id
    ) AS repos
FROM contract_activity AS a
GROUP BY a.network, a.contract_id
ORDER BY sum(a.invocations) DESC
LIMIT 200
