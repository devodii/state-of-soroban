INSERT INTO frictions (run_id, cluster, terms, size, cohesion, parts, medoids)
VALUES ($1, $2, $3, $4, $5, $6, $7)
ON CONFLICT (run_id, cluster) DO NOTHING
