UPDATE catalog_candidates
SET status = 'accepted'
WHERE kind = 'query' AND status = 'open' AND repos >= $1
