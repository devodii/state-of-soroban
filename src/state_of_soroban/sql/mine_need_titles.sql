SELECT
    r.owner,
    i.title
FROM issues AS i
INNER JOIN repos AS r ON i.repo = r.full_name
WHERE (r.is_stellar OR r.is_soroban) AND NOT r.is_fork
UNION ALL
SELECT
    'qa:' || q.source || ':' || q.id AS owner,
    q.title
FROM qa_posts AS q
