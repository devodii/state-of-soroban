SELECT signature
FROM catalog_candidates
WHERE kind = 'query' AND status = 'accepted'
ORDER BY repos DESC
