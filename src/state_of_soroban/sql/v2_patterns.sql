WITH stats AS (
    SELECT
        m.pattern,
        count(DISTINCT m.repo) AS repos,
        count(*) AS occurrences
    FROM pattern_matches AS m
    WHERE NOT m.in_test
    GROUP BY m.pattern
),

linked AS (
    SELECT
        pattern,
        array_agg(proposal ORDER BY proposal) AS proposals
    FROM proposal_patterns
    GROUP BY pattern
)

SELECT
    p.id,
    p.category,
    p.description,
    p.origin,
    p.status,
    p.diff,
    ex.repo AS sample_repo,
    ex.path AS sample_path,
    ex.snippet AS sample,
    l.proposals,
    coalesce(s.repos, 0) AS repos,
    coalesce(s.occurrences, 0) AS occurrences
FROM patterns AS p
LEFT JOIN stats AS s ON p.id = s.pattern
LEFT JOIN linked AS l ON p.id = l.pattern
LEFT JOIN LATERAL (
    SELECT
        m.repo,
        m.path,
        left(m.snippet, 700) AS snippet
    FROM pattern_matches AS m
    WHERE m.pattern = p.id AND NOT m.in_test
    ORDER BY m.repo ASC, m.path ASC
    LIMIT 1
) AS ex ON TRUE
ORDER BY coalesce(s.repos, 0) DESC, p.id ASC
