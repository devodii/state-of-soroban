(
    SELECT
        e.callee AS other,
        'out' AS direction,
        sum(e.calls) AS calls
    FROM contract_edges AS e
    WHERE e.network = $1 AND e.caller = $2
    GROUP BY e.callee
    ORDER BY sum(e.calls) DESC
    LIMIT $3
)
UNION ALL
(
    SELECT
        e.caller AS other,
        'in' AS direction,
        sum(e.calls) AS calls
    FROM contract_edges AS e
    WHERE e.network = $1 AND e.callee = $2
    GROUP BY e.caller
    ORDER BY sum(e.calls) DESC
    LIMIT $3
)
