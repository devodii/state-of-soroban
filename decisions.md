# Decisions

- **Two repos.** state-of-soroban finds and reads Soroban repos. soroban-wrapped shows on-chain stats. They share nothing at runtime.
- **Soroban only first.** The pipeline stops at a complete set of Soroban repos with their commits, issues and pull requests. Needs, gap analysis, the graph, the web app and the chain lookups were removed on 2026-11-24 and live at the git tag `legacy-full-pipeline`. The friction layer comes after indexing is complete.
- **Fresh start.** The database is built from `db/schema` on an empty Postgres. Old migrations were deleted. An earlier run's 8,423 confirmed Soroban repos are kept only as an answer key in `seeds/known-soroban-repos.txt`.
- **Declarative schema.** Tables are plain files under `db/schema`. `schema apply` plans the difference with pgschema and applies it, `schema verify` fails on drift.
- **Done is measured.** Four signals decide when to stop indexing (see the README). Recall is estimated from the overlap of independent channels (capture and recapture), not guessed.
- **Never read a repo twice.** Checkpoints per unit of work, per artifact file and per Actions run. Artifacts are deleted only after a successful import.
- **Extraction runs on Actions.** Clone and parse on runners (fast link), shards by index modulo count, queue on an orphan `queue` branch. The repo is public so runs are free.
- **Concurrency.** Discovery runs every query at once. Metadata, history, dispatch, harvest, sweep and dependents run as independent loops sharing one connection pool. Tokens rotate, rate limits back off, a lost connection waits and resumes.
- **No Stellar Expert.** Paywalled and rate limited.
- **Code style.** Pydantic models only, SQL in files, settings and lists in the workflow yaml, no comments except escape hatches.
