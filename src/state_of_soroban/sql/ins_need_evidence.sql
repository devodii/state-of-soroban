INSERT INTO need_evidence (need, kind, repo, ref, relevance, title, snippet, url, created_at)
VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
ON CONFLICT (need, kind, repo, ref) DO NOTHING
