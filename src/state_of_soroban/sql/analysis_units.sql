SELECT
    kind,
    repo,
    ref,
    family,
    owner,
    title,
    body
FROM evidence
WHERE NOT is_bot
ORDER BY kind, repo, ref
