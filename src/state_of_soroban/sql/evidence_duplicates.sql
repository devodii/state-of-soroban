UPDATE evidence AS e
SET dup_owners = d.owners
FROM (
    SELECT
        dup_key,
        count(DISTINCT owner) AS owners
    FROM evidence
    GROUP BY dup_key
) AS d
WHERE e.dup_key = d.dup_key
