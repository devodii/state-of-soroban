SELECT
    n.id,
    n.title,
    n.category,
    n.origin,
    n.status,
    n.score,
    n.summary,
    n.demand,
    n.signals,
    n.evidence,
    n.rfp,
    n.scored_at,
    (
        SELECT count(*) FROM comments AS c
        WHERE c.target_kind = 'need' AND c.target_id = n.id
    ) AS comments
FROM tooling_needs AS n
WHERE n.id = $1
