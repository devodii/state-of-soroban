# state-of-soroban

The research and indexing product. It is a separate codebase from soroban-wrapped (the public on-chain stats app) so the indexers can run on their own machine and be improved independently. It holds the GitHub scraping, discovery, extraction, ecosystem graph, tooling needs and gap analysis, with its own Postgres on port 5443 (copied from the original database, including copies of the chain tables used for linking).

To resume on any machine: `cp .env.example .env`, `docker compose up -d --wait db`, `uv sync`, `uv run state-of-soroban drive`, and `uv run state-of-soroban serve` for the UI. Ports: db 5443, api 8788, web dev 5174, storybook 6007, so it runs beside soroban-wrapped.

Indexes every public Soroban contract repo and the chain, stores analysis-grade data in its own Postgres, and lets the data propose what developers should not have to rewrite by hand.

The idea: mine the boilerplate everyone hand-writes (TTL bumps, auth guards, init checks, error plumbing, events, test setup), score each finding by how independently it is reused, and tie it to real bugs. Proposals come from the data. The YAML catalog only holds seeds to test.

## Quick start

```sh
cp .env.example .env            # put your GitHub tokens in GITHUB_TOKENS, comma separated
docker compose up -d --wait db
uv sync
uv run state-of-soroban schema apply
uv run state-of-soroban drive    # autopilot, runs every stage and keeps going
uv run state-of-soroban serve    # live UI on http://localhost:8788
```

The public web app lives in `web/` (see `decisions.md`). Build it with `cd web && pnpm install && pnpm build`, then `serve` hosts it at http://localhost:8788/app. For development run `pnpm dev` in `web` (proxies `/api` to :8788) and `pnpm storybook` for the component workbench. After an API change run `pnpm types`.

Add more tokens to `.env` at any time. Running jobs pick them up within 30 seconds.

## What runs

Defined in `workflow/workflow.yaml`, in order:

| Stage | What it does |
|---|---|
| `catalog` | loads the seed patterns, bug classes, libraries and proposals |
| `discover` | GitHub search (text and content) and crates.io, checkpointed per page |
| `metadata` | stars, languages, last push, size, in batched GraphQL |
| `clone` | commits-only sparse git fetch, parses the Rust, matches patterns, reads commits, networks and contract ids |
| `history` | issues, pull requests and releases through GraphQL |
| `sweep` | lists every repo of each confirmed owner to find siblings |
| `chain` | looks every contract id up on mainnet and testnet RPC for liveness, wasm, spec and metadata |
| `lake` | imports finished ledger-archive runs from GitHub Actions |
| `mine` | finds uncovered clusters, idioms, macros, vocabularies and fix terms in the corpus |
| `score` | scores seeds and mined proposals with the same reuse formula |
| `graph` | builds the proposal, repo, library and contract graph |

Every unit of work is checkpointed, so a dropped connection or a crash resumes instead of restarting. `drive` supervises all of it.

## On-chain history

The year of ledger history is too big to download. `.github/workflows/lake.yml` reads the public AWS ledger archive on GitHub runners, keeps only call events and daily totals, and uploads small parquet files. `state-of-soroban lake-import` (or the `lake` stage) loads them. See `decisions.md` for the measured speeds.

```sh
gh workflow run lake.yml -f network=mainnet -f start=2026-01-01 -f end=2026-04-30
```

## Layout

```
workflow/            the YAML workflow and the catalog (seeds, bug classes, libraries)
db/schema, db/migrations   pgschema schema files and numbered migrations
src/state_of_soroban/
  extract/           rust parser, pattern matcher, cargo, git, networks
  chain/             rpc, wasm spec reader, ledger archive summariser
  stages/            one module per workflow stage
  sql/               every query
  ui/index.html      the live research page
```

See `decisions.md` for the choices made and why, and `ROADMAP.md` for what is next.
