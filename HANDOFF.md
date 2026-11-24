# Handoff to the bigger machine (2026-11-24)

## Start here

1. `gh repo clone devodii/state-of-soroban && cd state-of-soroban`, then run `claude`. It reads `CLAUDE.md` for the rules.
2. Install Docker, uv and gh (`gh auth login` as `devodii`). `cp .env.example .env` and put the three GitHub tokens in `GITHUB_TOKENS`. Tokens are never in git.
3. `docker compose up -d --wait db`, `uv sync`, `uv run state-of-soroban schema apply` builds the database from scratch.
4. `uv run state-of-soroban drive` under `caffeinate` or a service. Check Actions are enabled on the repo (it is public so runs are free).
5. Watch `uv run state-of-soroban ready`. When it passes, `out/READY.md` is written and the autopilot stops.

There is no data transfer. The database starts empty and the pipeline rebuilds it. `seeds/known-soroban-repos.txt` holds the 8,423 Soroban repos an earlier run found, used only as an answer key for the recall signal. The old database stays on the first machine.

## Pipeline now

Soroban discovery only: `catalog`, `discover`, `dependents`, `metadata`, `dispatch` and `harvest` (extraction on Actions runners), `history`, `sweep`. Everything runs concurrently from the `autopilot` block of `workflow/workflow.yaml`. Removed on purpose (recover from the git tag `legacy-full-pipeline`): the web app and API, ecosystem fingerprints, needs and RFPs, gap analysis, the graph, mining and scoring, QA ingestion, chain lookups, old migrations.

## When is indexing finished

`state-of-soroban ready` prints four signals, all must pass: nothing waiting for metadata, extraction or history; no new Soroban repo in the last 24 hours of running; estimated recall at least 99 percent from the overlap of independent channels (code search, topic search, dependency graph); at least 99 percent of the known list rediscovered. Thresholds are under `readiness` in the workflow yaml. If it has not passed after two or three days, read which signal is stuck and add the missing discovery channel (forks, contributors, build-workflow users, crates.io owners) instead of waiting.

## Next: the Friction Ledger (build after `ready` passes)

A stage that finds recurring problems by itself and keeps counting, so nobody has to read a summary. Sources: fix commits (`commits.is_fix`), issue and pull request titles (`issues`); Soroban repos only, forks excluded. Normalise (strip `fix:` prefixes, numbers, hashes, links, stop words from config), take 2 to 4 word phrases, count distinct repos and owners per phrase. At 10 or more distinct repos (`min_repos`, configurable) a phrase becomes a friction with the date it crossed, and every later run updates its count. Merge overlapping phrases. Map each friction to the bug classes in the catalog or open a new candidate, score it automatically, and keep a count history so growth is visible. Tables: `frictions`, `friction_history`, `friction_evidence`. Noise words and a mute list go in the workflow yaml. Run it every few hours with the autopilot. The old needs, gaps and RFP code at `legacy-full-pipeline` can be mined for the scoring and the gap check.

## Open asks

1. Make discovery recall provable: build more independent channels (forks, contributors, build-workflow users, crates.io owners) until the recall signal reaches 99 percent.
2. Friction Ledger as above, then re-add a presentation layer only once it has results.
3. Never read a repo twice and keep every stage resumable.

## Lessons

GitHub secondary rate limits hit when probing the API hard. GraphQL history totals time out in large batches, keep batches around 40. Do not run heavy analytics while importing. Extraction on runners is about 300 times faster than on a slow home link.
