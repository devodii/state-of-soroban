SELECT count(*) AS stale
FROM source_files
WHERE content IS NOT NULL AND analysed_with IS DISTINCT FROM $1
