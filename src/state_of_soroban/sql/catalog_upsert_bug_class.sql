INSERT INTO bug_classes (id, name, description, severity)
VALUES ($1, $2, $3, $4)
ON CONFLICT (id) DO UPDATE SET
    name = excluded.name,
    description = excluded.description,
    severity = excluded.severity
