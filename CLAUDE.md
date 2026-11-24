# state-of-soroban

Standalone indexer and research product. Right now it does one job: discover every public Soroban repo (window 2026-01-01 to today) and read their commits, issues and pull requests into its own Postgres. When `state-of-soroban ready` passes, the Friction Ledger is built on top (recurring problems found and counted automatically). The on-chain stats product is a different repo (`devodii/soroban-wrapped`). Read `HANDOFF.md` first for what to do next. The older full pipeline (web app, needs, gaps, graph, chain) is at the git tag `legacy-full-pipeline`, restore pieces from there when needed.

## Rules the user has set (follow them exactly)

- Commits: one sentence, `<type>: <lowercase imperative subject>`, types feat fix refactor chore perf test docs style build ci. No scope, no body, no em dashes, no AI or Co-Authored-By lines. Atomic commits, one logical change each. Push to `main` right after committing without asking. Run the formatter first (`ruff format`, `sqlfluff fix` for sql, `pnpm exec prettier --write` in `web`).
- Python: pydantic `BaseModel` for every structured type, never dataclasses, NamedTuple or TypedDict. No comments in code except a short line for a non-obvious escape hatch. SQL lives in `src/state_of_soroban/sql/*.sql`, loaded with `load_sql`. Configuration and lists live in `workflow/workflow.yaml` and `workflow/catalog/*.yaml`, never hardcoded in code. asyncpg pool has a jsonb codec: pass Python objects, not json strings.
- Web: `import * as React from 'react'` and use `React.*`. Components in `ui/Button/Button.tsx`, `Button.stories.tsx`, `Button.scss`. Use `moment` directly (no util wrappers). Use packages, do not hand-roll. Types are generated from OpenAPI (`pnpm types`), never written by hand.
- Keep few tests, only the most important. During big builds run the formatter often and the full checks only once in a while. CI on GitHub still runs on every push, fix red.
- Resumable first: every unit of work has a row in `checkpoints`. Never index or fetch the same repo twice. Network (mainnet or testnet) is recorded everywhere. No Stellar Expert.
- Never print GitHub tokens. Never put the user's tokens into GitHub secrets without asking. Never touch the hackproof repo or its databases. Never touch other projects' Docker volumes.
- The user hates long reports: answer in short plain sentences, give frequent concise updates, and do not wait to be told to continue. Keep a running list of their asks and never drop one.
- Subagents make mistakes. Do the work in the main thread unless the user asks otherwise, and verify what a subagent claims.

## How Actions results reach the database

Extraction runs on GitHub Actions (`.github/workflows/extract.yml`), which clones repos in shards and uploads `shard-N.jsonl.gz` artifacts. The Actions runners never touch the database. `dispatch` starts a run when enough repos are queued, and `harvest` (on this machine) downloads finished runs with `gh`, writes each line to Postgres through `store`, records `extract-run` and `extract-file` checkpoints so nothing is imported twice, then deletes the artifacts.

## Run

`cp .env.example .env` (add `GITHUB_TOKENS`, comma separated), `docker compose up -d --wait db` (empty database), `uv sync`, `uv run state-of-soroban schema apply`, `uv run state-of-soroban drive` (autopilot), `uv run state-of-soroban ready` (is indexing complete?). Database port 5443. There are no migration files: tables are declared under `db/schema` and applied with pgschema.
