WITH members AS (
    SELECT DISTINCT
        m.repo,
        m.path
    FROM unnest($1::text[], $2::text[]) AS m (repo, path)
),

member_repos AS (
    SELECT DISTINCT repo FROM members
),

fixes AS (
    SELECT DISTINCT
        cf.repo,
        cf.sha
    FROM commit_files AS cf
    INNER JOIN commits AS c ON cf.repo = c.repo AND cf.sha = c.sha
    INNER JOIN members AS mm ON cf.repo = mm.repo AND cf.path = mm.path
    WHERE
        c.is_fix
        AND c.touches_rust
        AND c.message !~* '(typo|\mci\M|lint|format|readme|\mdocs?\M|workflow|dependabot|\mbump\M|changelog)'
)

SELECT
    (
        SELECT count(DISTINCT r.owner)
        FROM member_repos AS mr
        INNER JOIN repos AS r ON mr.repo = r.full_name
    ) AS owners,
    (SELECT count(*) FROM member_repos) AS repos,
    (
        SELECT count(*)
        FROM member_repos AS mr
        INNER JOIN repos AS r ON mr.repo = r.full_name
        WHERE r.pushed_at >= now() - make_interval(days => $3)
    ) AS recent_repos,
    (
        SELECT count(DISTINCT mr.repo)
        FROM member_repos AS mr
        INNER JOIN repo_contract_refs AS rc ON mr.repo = rc.repo
        INNER JOIN deployed_contracts AS d
            ON rc.contract_id = d.contract_id AND d.network = 'mainnet'
    ) AS mainnet_repos,
    (
        SELECT count(DISTINCT mr.repo)
        FROM member_repos AS mr
        INNER JOIN crate_dependencies AS cd ON mr.repo = cd.repo
        WHERE cd.name = any($4::text[])
    ) AS adopted_repos,
    (SELECT count(*) FROM fixes) AS fix_commits,
    (
        SELECT count(*)
        FROM issues AS i
        INNER JOIN member_repos AS mr ON i.repo = mr.repo
        WHERE i.is_bug
    ) AS bug_issues
