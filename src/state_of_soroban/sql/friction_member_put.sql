INSERT INTO friction_members (run_id, kind, repo, ref, cluster, sim)
VALUES ($1, $2, $3, $4, $5, $6)
ON CONFLICT (run_id, kind, repo, ref) DO NOTHING
