# state-of-soroban

Finds every public Soroban repo and reads what its developers struggle with. It is the research and indexing product; the public on-chain stats page is a separate repo, `soroban-wrapped`.

Right now the pipeline does one job: discovery to a complete, trustworthy set of Soroban repos with their commits, issues and pull requests. When `state-of-soroban ready` says the set is complete, the friction layer (recurring problems, counted and scored automatically) is built on top of it.

## Run

```sh
cp .env.example .env                     # put GITHUB_TOKENS in it
docker compose up -d --wait db           # empty Postgres 17 on port 5443
uv sync
uv run state-of-soroban schema apply     # builds every table from db/schema
uv run state-of-soroban drive            # autopilot, resumes from checkpoints after any crash
uv run state-of-soroban ready            # is indexing complete enough to move on?
```

## What runs

Defined in `workflow/workflow.yaml`.

| Stage | What it does |
|---|---|
| `catalog` | loads the seed patterns and bug classes |
| `discover` | GitHub text and code search and crates.io, every query in parallel, checkpointed per page |
| `dependents` | crawls the GitHub dependency graph of the Soroban SDK crates |
| `metadata` | stars, languages, last push and size in batched GraphQL |
| `dispatch` and `harvest` | clone and parse on Actions runners (`extract.yml`), import the artifacts once |
| `history` | commits, issues, pull requests and releases of confirmed Soroban repos |
| `sweep` | lists every repo of each confirmed owner |
| `clone` | the same extraction on this machine, for small runs |

The autopilot (`drive`) runs these concurrently as configured under `autopilot` in the workflow file. It never reads the same repo twice: every unit of work has a row in `checkpoints`.

## Knowing when to stop

`state-of-soroban ready` prints the signals, and `drive` writes `out/READY.md` and stops when all pass:

1. No relevant repo is waiting for metadata, extraction or history.
2. No new Soroban repo was found in the last 24 hours of running.
3. Estimated recall of at least 99 percent, from the overlap between independent discovery channels (code search, topic search, dependency graph).
4. At least 99 percent of the repos in `seeds/known-soroban-repos.txt` (an answer key from an earlier run) were found again.

Thresholds live under `readiness` in the workflow file.

## Layout

`src/state_of_soroban` the code, `src/state_of_soroban/sql` every query, `db/schema` the tables (declarative, applied with pgschema, no migration files), `workflow` the pipeline and catalog yaml, `seeds` the answer key. The earlier full pipeline (web app, needs, gaps, graph, chain) is kept at the git tag `legacy-full-pipeline`.
