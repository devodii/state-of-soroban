DELETE FROM pattern_matches
WHERE repo = $1 AND path = $2
