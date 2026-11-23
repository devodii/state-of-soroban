SELECT
    repo,
    path,
    content
FROM source_files
WHERE content IS NOT NULL AND analysed_with IS DISTINCT FROM $1
ORDER BY repo ASC, path ASC
LIMIT $2
