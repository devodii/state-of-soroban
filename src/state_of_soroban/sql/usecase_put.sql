INSERT INTO usecases (run_id, usecase, size, terms)
VALUES ($1, $2, $3, $4)
ON CONFLICT (run_id, usecase) DO NOTHING
