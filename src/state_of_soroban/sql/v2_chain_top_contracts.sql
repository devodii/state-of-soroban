WITH top AS (
    SELECT
        a.network,
        a.contract_id,
        sum(a.invocations) AS invocations,
        sum(a.successful) AS successful,
        max(a.callers) AS peak_daily_callers,
        count(*) AS active_days,
        min(a.day) AS first_day,
        max(a.day) AS last_day
    FROM contract_activity AS a
    GROUP BY a.network, a.contract_id
    ORDER BY sum(a.invocations) DESC
    LIMIT $1
)

SELECT
    top.network,
    top.contract_id,
    top.invocations,
    top.successful,
    top.peak_daily_callers,
    top.active_days,
    top.first_day,
    top.last_day,
    d.live,
    (
        SELECT array_agg(DISTINCT l.repo)
        FROM repo_contract_links AS l
        WHERE l.contract_id = top.contract_id AND l.link IN ('verified', 'deployment', 'code')
    ) AS repos
FROM top
LEFT JOIN deployed_contracts AS d ON top.network = d.network AND top.contract_id = d.contract_id
ORDER BY top.invocations DESC
