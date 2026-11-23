UPDATE tooling_needs
SET
    score = $2,
    demand = $3,
    evidence = $4,
    rfp = $5,
    scored_at = now()
WHERE id = $1
