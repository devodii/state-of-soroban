INSERT INTO proposal_repos (proposal, repo, weight)
SELECT
    pp.proposal,
    m.repo,
    count(*)
FROM proposal_patterns AS pp
INNER JOIN pattern_matches AS m ON pp.pattern = m.pattern AND NOT m.in_test
WHERE pp.role IN ('boilerplate', 'footgun')
GROUP BY pp.proposal, m.repo
ON CONFLICT (proposal, repo) DO UPDATE SET weight = excluded.weight
