SELECT DISTINCT
    f.repo,
    f.path
FROM functions AS f
WHERE
    f.is_contract_fn
    AND NOT f.is_test
    AND (SELECT string_agg(c, ' ' ORDER BY c) FROM unnest(f.calls) AS c) = $1
