WITH latest AS (
    SELECT run_id FROM analysis_runs
    WHERE
        EXISTS (
            SELECT 1 FROM usecases AS u
            WHERE u.run_id = analysis_runs.run_id
        )
    ORDER BY created_at DESC
    LIMIT 1
),

base AS (
    SELECT
        ru.usecase,
        count(*)::float / sum(count(*)) OVER () AS share
    FROM repo_usecases AS ru
    WHERE ru.run_id = (SELECT run_id FROM latest)
    GROUP BY ru.usecase
),

hit AS (
    SELECT
        ru.usecase,
        count(DISTINCT e.family) AS families
    FROM friction_members AS m
    INNER JOIN evidence AS e ON m.kind = e.kind AND m.repo = e.repo AND m.ref = e.ref
    INNER JOIN repo_usecases AS ru
        ON e.repo = ru.repo AND ru.run_id = (SELECT run_id FROM latest)
    WHERE
        m.run_id = (
            SELECT run_id FROM analysis_runs
            ORDER BY created_at DESC LIMIT 1
        ) AND m.cluster = $1
    GROUP BY ru.usecase
)

SELECT
    u.usecase,
    u.terms,
    h.families,
    (h.families::float / sum(h.families) OVER ()) / b.share AS lift
FROM hit AS h
INNER JOIN base AS b ON h.usecase = b.usecase
INNER JOIN usecases AS u ON h.usecase = u.usecase AND u.run_id = (SELECT run_id FROM latest)
WHERE h.families >= $2
ORDER BY lift DESC
LIMIT 6
