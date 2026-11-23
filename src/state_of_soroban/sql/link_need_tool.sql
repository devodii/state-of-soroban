INSERT INTO need_tools (need, tool, relation, relevance)
VALUES ($1, $2, $3, $4)
ON CONFLICT (need, tool) DO UPDATE SET relation = excluded.relation, relevance = excluded.relevance
