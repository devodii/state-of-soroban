DELETE FROM need_tools
WHERE need IN (
    SELECT id FROM tooling_needs
    WHERE origin = 'seed'
)
