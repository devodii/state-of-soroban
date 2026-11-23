SELECT
    b.id,
    b.name,
    b.description,
    b.severity
FROM proposal_bug_classes AS pb
INNER JOIN bug_classes AS b ON pb.bug_class = b.id
WHERE pb.proposal = $1
ORDER BY b.name ASC
