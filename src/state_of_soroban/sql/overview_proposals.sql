SELECT
    id,
    name,
    kind,
    summary,
    sketch,
    origin,
    status,
    score,
    covered_by,
    evidence,
    scored_at,
    (
        SELECT count(*) FROM comments AS c
        WHERE c.target_kind = 'proposal' AND c.target_id = proposals.id
    ) AS comments
FROM proposals
ORDER BY score DESC
LIMIT 400
