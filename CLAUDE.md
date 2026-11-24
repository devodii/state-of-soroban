# state-of-soroban

Standalone indexer and research product. It indexes every public Soroban contract repo (window 2026-01-01 to today) plus ecosystem repos into its own Postgres, mines what developers rewrite or struggle with, scores tooling needs and writes RFP drafts. The on-chain stats product is a different repo (`devodii/soroban-wrapped`). Read `HANDOFF.md` first for the current state and what to do next.

## Rules the user has set (follow them exactly)

- Commits: one sentence, `<type>: <lowercase imperative subject>`, types feat fix refactor chore perf test docs style build ci. No scope, no body, no em dashes, no AI or Co-Authored-By lines. Atomic commits, one logical change each. Push to `main` right after committing without asking. Run the formatter first (`ruff format`, `sqlfluff fix` for sql, `pnpm exec prettier --write` in `web`).
- Python: pydantic `BaseModel` for every structured type, never dataclasses, NamedTuple or TypedDict. No comments in code except a short line for a non-obvious escape hatch. SQL lives in `src/state_of_soroban/sql/*.sql`, loaded with `load_sql`. Configuration and lists live in `workflow/workflow.yaml` and `workflow/catalog/*.yaml`, never hardcoded in code. asyncpg pool has a jsonb codec: pass Python objects, not json strings.
- Web: `import * as React from 'react'` and use `React.*`. Components in `ui/Button/Button.tsx`, `Button.stories.tsx`, `Button.scss`. Use `moment` directly (no util wrappers). Use packages, do not hand-roll. Types are generated from OpenAPI (`pnpm types`), never written by hand.
- Keep few tests, only the most important. During big builds run the formatter often and the full checks only once in a while. CI on GitHub still runs on every push, fix red.
- Resumable first: every unit of work has a row in `checkpoints`. Never index or fetch the same repo twice. Network (mainnet or testnet) is recorded everywhere. No Stellar Expert.
- Never print GitHub tokens. Never put the user's tokens into GitHub secrets without asking. Never touch the hackproof repo or its databases. Never touch other projects' Docker volumes.
- The user hates long reports: answer in short plain sentences, give frequent concise updates, and do not wait to be told to continue. Keep a running list of their asks and never drop one.
- Subagents make mistakes. Do the work in the main thread unless the user asks otherwise, and verify what a subagent claims.

## Run

`cp .env.example .env` (add `GITHUB_TOKENS`, comma separated), `docker compose up -d --wait db`, `uv sync`, `uv run state-of-soroban schema apply`, `uv run state-of-soroban drive` (autopilot), `uv run state-of-soroban serve` (api on 8788). Ports: db 5443, api 8788, vite 5174, storybook 6007.
