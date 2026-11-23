INSERT INTO tool_catalog (
    id, name, category, url, description, ecosystems, packages, keywords, solves
)
VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
ON CONFLICT (id) DO UPDATE SET
    name = excluded.name,
    category = excluded.category,
    url = excluded.url,
    description = excluded.description,
    ecosystems = excluded.ecosystems,
    packages = excluded.packages,
    keywords = excluded.keywords,
    solves = excluded.solves
