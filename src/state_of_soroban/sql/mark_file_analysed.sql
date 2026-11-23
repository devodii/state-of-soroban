UPDATE source_files
SET analysed_with = $3
WHERE repo = $1 AND path = $2
