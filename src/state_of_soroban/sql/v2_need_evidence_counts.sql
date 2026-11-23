SELECT
    kind,
    count(*) AS total
FROM need_evidence
WHERE need = $1
GROUP BY kind
ORDER BY count(*) DESC
