SELECT
    pp.pattern AS id,
    pp.role,
    p.category,
    p.description
FROM proposal_patterns AS pp
INNER JOIN patterns AS p ON pp.pattern = p.id
WHERE pp.proposal = $1
ORDER BY pp.role ASC, pp.pattern ASC
