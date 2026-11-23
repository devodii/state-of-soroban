WITH q AS (SELECT websearch_to_tsquery('english', $1) AS query),

issue_hits AS (
    SELECT
        r.owner,
        i.repo,
        i.state,
        i.created_at,
        i.reactions + i.comments AS engagement,
        ((i.title || ' ' || left(coalesce(i.body, ''), 2500)) ~* $8 AND i.title !~* $9) AS pain
    FROM issues AS i
    INNER JOIN repos AS r ON i.repo = r.full_name
    CROSS JOIN q
    WHERE
        i.search @@ q.query
        AND ts_rank_cd(i.search, q.query, 32) >= $6
        AND (r.is_stellar OR r.is_soroban)
        AND NOT r.is_fork
),

doc_hits AS (
    SELECT
        r.owner,
        d.repo
    FROM repo_documents AS d
    INNER JOIN repos AS r ON d.repo = r.full_name
    CROSS JOIN q
    WHERE
        d.search @@ q.query
        AND ts_rank_cd(d.search, q.query, 32) >= $7
        AND d.kind IN ('readme', 'docs', 'script', 'build', 'ci', 'docker', 'env')
        AND (r.is_stellar OR r.is_soroban)
        AND NOT r.is_fork
),

custom_hits AS (
    SELECT
        r.owner,
        e.repo
    FROM ecosystem_dependencies AS e
    INNER JOIN repos AS r ON e.repo = r.full_name
    WHERE lower(e.name) = any($2::text[]) AND NOT r.is_fork
    UNION
    SELECT
        r.owner,
        d.repo
    FROM repo_documents AS d
    INNER JOIN repos AS r ON d.repo = r.full_name
    WHERE d.path ~* $3 AND (r.is_stellar OR r.is_soroban) AND NOT r.is_fork
),

everyone AS (
    SELECT
        owner,
        repo
    FROM issue_hits
    UNION
    SELECT
        owner,
        repo
    FROM doc_hits
    UNION
    SELECT
        owner,
        repo
    FROM custom_hits
)

SELECT
    (SELECT count(DISTINCT owner) FROM everyone) AS owners,
    (SELECT count(DISTINCT repo) FROM everyone) AS repos,
    (SELECT count(*) FROM issue_hits) AS issues,
    (
        SELECT count(*)
        FROM qa_posts AS p
        CROSS JOIN q
        WHERE p.search @@ q.query AND ts_rank_cd(p.search, q.query, 32) >= $6
    ) AS questions,
    (
        SELECT count(*) FROM issue_hits
        WHERE pain
    ) AS pain_issues,
    (
        SELECT count(DISTINCT owner) FROM issue_hits
        WHERE pain
    ) AS pain_owners,
    (
        SELECT count(*) FROM issue_hits
        WHERE state = 'open'
    ) AS open_issues,
    (SELECT count(*) FROM doc_hits) AS documents,
    (SELECT count(DISTINCT repo) FROM custom_hits) AS custom_repos,
    (
        SELECT count(*) FROM issue_hits
        WHERE owner = any($4::text[])
    ) AS official,
    (
        SELECT count(*) FROM issue_hits
        WHERE created_at >= now() - make_interval(days => $5)
    ) AS recent,
    (SELECT count(*) FROM issue_hits) AS dated,
    (SELECT coalesce(sum(engagement), 0) FROM issue_hits) AS engagement,
    (
        SELECT count(*)
        FROM issues AS i
        INNER JOIN repos AS r ON i.repo = r.full_name
        WHERE (r.is_stellar OR r.is_soroban) AND NOT r.is_fork
    ) AS corpus_issues
