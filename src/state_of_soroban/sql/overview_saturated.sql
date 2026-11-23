SELECT count(*) AS saturated
FROM checkpoints
WHERE job = 'discover' AND cursor ->> 'saturated' = 'true'
