UPDATE catalog_candidates
SET status = 'rejected'
WHERE kind = 'query' AND status IN ('open', 'accepted') AND signature = ANY($1::text[])
