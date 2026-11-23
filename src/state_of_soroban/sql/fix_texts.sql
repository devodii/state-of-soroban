SELECT
    r.owner,
    c.message AS text,
    TRUE AS is_fix
FROM commits AS c
INNER JOIN repos AS r ON c.repo = r.full_name
WHERE c.is_fix AND NOT r.is_fork
UNION ALL
SELECT
    r.owner,
    i.title || ' ' || left(coalesce(i.body, ''), 600) AS text,
    TRUE AS is_fix
FROM issues AS i
INNER JOIN repos AS r ON i.repo = r.full_name
WHERE i.is_bug AND NOT r.is_fork
UNION ALL
SELECT
    r.owner,
    c.message AS text,
    FALSE AS is_fix
FROM commits AS c
INNER JOIN repos AS r ON c.repo = r.full_name
WHERE NOT c.is_fix AND NOT r.is_fork
