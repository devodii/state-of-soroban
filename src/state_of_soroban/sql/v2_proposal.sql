SELECT
    p.id,
    p.name,
    p.kind,
    p.summary,
    p.sketch,
    p.origin,
    p.status,
    p.score,
    p.covered_by,
    p.scored_at,
    p.min_repos,
    p.evidence,
    (
        SELECT count(*) FROM comments AS c
        WHERE c.target_kind = 'proposal' AND c.target_id = p.id
    ) AS comments
FROM proposals AS p
WHERE p.id = $1
