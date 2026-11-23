INSERT INTO repos (
    full_name, url, owner, owner_type, owner_location, description, homepage,
    topics, language, languages, license, stars, forks, watchers, open_issues,
    size_kb, default_branch, archived, is_fork, parent_full_name, is_template,
    created_at, pushed_at, window_commits, total_commits, head_sha
)
VALUES (
    $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17,
    $18, $19, $20, $21, $22, $23, $24, $25, $26
)
ON CONFLICT (full_name) DO UPDATE SET
    url = excluded.url,
    owner = excluded.owner,
    owner_type = excluded.owner_type,
    owner_location = excluded.owner_location,
    description = excluded.description,
    homepage = excluded.homepage,
    topics = excluded.topics,
    language = excluded.language,
    languages = excluded.languages,
    license = excluded.license,
    stars = excluded.stars,
    forks = excluded.forks,
    watchers = excluded.watchers,
    open_issues = excluded.open_issues,
    size_kb = excluded.size_kb,
    default_branch = excluded.default_branch,
    archived = excluded.archived,
    is_fork = excluded.is_fork,
    parent_full_name = excluded.parent_full_name,
    is_template = excluded.is_template,
    created_at = excluded.created_at,
    pushed_at = excluded.pushed_at,
    window_commits = excluded.window_commits,
    total_commits = excluded.total_commits,
    head_sha = excluded.head_sha
