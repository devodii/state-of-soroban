INSERT INTO repo_documents (repo, path, kind, size, blob_sha, text_content)
VALUES ($1, $2, $3, $4, $5, $6)
ON CONFLICT (repo, path) DO NOTHING
