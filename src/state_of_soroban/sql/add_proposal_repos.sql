INSERT INTO proposal_repos (proposal, repo)
SELECT
    $1,
    unnest($2::text[])
ON CONFLICT (proposal, repo) DO NOTHING
