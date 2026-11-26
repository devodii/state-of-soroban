SELECT
    r.full_name,
    r.description,
    r.topics,
    (
        SELECT left(d.text_content, 1500) FROM repo_documents AS d
        WHERE d.repo = r.full_name AND d.kind = 'readme'
        ORDER BY length(d.path)
        LIMIT 1
    ) AS readme
FROM repos AS r
WHERE r.is_soroban AND NOT r.is_fork
