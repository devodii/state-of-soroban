SELECT coalesce(avg(relevance), 0)
FROM (
    SELECT relevance
    FROM need_evidence
    WHERE need = $1 AND kind IN ('issue', 'pull', 'document', 'question')
    ORDER BY relevance DESC
    LIMIT 20
) AS top
