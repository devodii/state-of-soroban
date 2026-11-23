SELECT
    kind,
    repo,
    title,
    snippet,
    url,
    relevance
FROM need_evidence
WHERE need = $1 AND kind IN ('issue', 'pull', 'document', 'question')
ORDER BY relevance DESC
LIMIT $2
