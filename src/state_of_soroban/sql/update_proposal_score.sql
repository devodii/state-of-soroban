UPDATE proposals
SET
    score = $2,
    evidence = $3,
    status = $4,
    scored_at = now()
WHERE id = $1
