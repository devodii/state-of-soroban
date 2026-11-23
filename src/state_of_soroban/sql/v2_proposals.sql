SELECT
    p.id,
    p.name,
    p.kind,
    p.summary,
    p.origin,
    p.status,
    p.score,
    p.covered_by,
    p.evidence -> 'components' AS components,
    p.evidence -> 'weighted' AS weighted,
    coalesce((p.evidence #>> '{metrics,repos}')::int, 0) AS repos,
    coalesce((p.evidence #>> '{metrics,owners}')::int, 0) AS owners,
    coalesce((p.evidence #>> '{metrics,mainnet_repos}')::int, 0) AS mainnet_repos,
    coalesce((p.evidence #>> '{metrics,fix_commits}')::int, 0) AS fix_commits,
    coalesce((p.evidence #>> '{metrics,occurrences}')::int, 0) AS occurrences,
    coalesce((p.evidence #>> '{copy_share}')::float, 0) AS copy_share,
    (
        SELECT count(*) FROM comments AS c
        WHERE c.target_kind = 'proposal' AND c.target_id = p.id
    ) AS comments
FROM proposals AS p
ORDER BY p.score DESC
LIMIT $1
