# Handoff to the bigger machine (written 2026-11-24)

## Where things are

- Repo: https://github.com/devodii/state-of-soroban (public, under the `devodii` account, so Actions minutes are free). Clone it, `cd` in and run `claude`.
- Database: a `pg_dump` in 1.9 GB parts with a `SHA256SUMS` file, copied over offline (AirDrop or a drive) into a folder on the new machine. Restore with `scripts/db-import.sh <folder>` (it also accepts a GitHub release tag). Do not copy `.pgdata` between machines unless both are the same CPU architecture and Postgres 17.
- Secrets are not in git. Create `.env` from `.env.example` and put the three GitHub tokens in `GITHUB_TOKENS`. Run `gh auth login` for the `devodii` account, the autopilot uses `gh` for Actions.
- Sibling product: `devodii/soroban-wrapped` (public, on-chain stats, stays on the first machine).

## First hour on the new machine

1. `gh repo clone devodii/state-of-soroban && cd state-of-soroban`
2. Install Docker, uv, pnpm, gh. `cp .env.example .env`, add tokens.
3. `scripts/db-import.sh <folder with the parts>`. It checks hashes, restores with 6 jobs and prints the repo count (expect about 707k).
4. `uv sync && uv run state-of-soroban schema verify` (must say the database matches).
5. The repo is public, so Actions runs are free. Check that Actions are enabled in its settings.
6. `uv run state-of-soroban drive` under `caffeinate` or a service. It resumes from checkpoints. Nothing needs reindexing.

## Do not reindex

Transfer the data and continue. The numbers at the pause (2026-11-22): repos discovered 706,978; with details 527,281; extracted (cloned and parsed) 82,288; confirmed Soroban 8,423; Stellar-related 16,602; ecosystem fingerprinted 126,423; found by the dependents crawl 3,762. These took days of runner time and API quota. Checkpoints tell every stage what is already done, so a restored database continues where it stopped. Run `reanalyse` only when patterns change, it works from stored source, not from GitHub.

## Plan (decided 2026-11-24)

1. Finish indexing the relevant repos first. Almost everything that matters is done: of 8,423 confirmed Soroban repos only 87 still need history; only about 345 relevant repos lack metadata, 16 await extraction and 314 await fingerprinting. The huge pending counts (176k without metadata, 400k unfingerprinted) are the generic-topic long tail and are processed last on purpose. Let it run in the background, do not wait for it.
2. Indexing is finished when relevant pending work is zero and discovery stops finding new Soroban repos (no new confirmed Soroban repo across the last three discovery cycles) and the recall check (open ask 2) reports at least 99 percent.
3. Then build and run the Friction Ledger over the discovered Soroban and Stellar repos.

## Open asks, in order

1. **Friction Ledger** (build after indexing of relevant repos is finished, not before). A stage that finds recurring problems by itself and keeps counting. Sources: fix commits (`commits.is_fix`), issue and PR titles, `qa_posts`; Soroban and Stellar repos only, forks excluded. Normalise (strip `fix:` prefixes, numbers, hashes, links, stop words from config), take 2 to 4 word phrases, count distinct repos and owners per phrase. At 10 or more distinct repos (configurable `min_repos`) the phrase becomes a friction with the date it crossed, and every later run updates its count. Merge overlapping phrases. Match each friction to existing bug classes and tooling needs and add to their evidence, or open a new candidate need. Then run the gap check (PR to an existing tool or build new) and score it automatically so the user never has to ask Claude to read a summary. Tables: `frictions`, `friction_history` (count over time), `friction_evidence` (links). Generic noise words and a mute list go in the workflow yaml. Expose "what breaks most" in the api and web app. Run with the other analytics stages every 3 hours.
2. Raise discovery recall to at least 99 percent. Done so far: dependents graph crawl (js-stellar-sdk lists in progress), on-chain `source_repo`, owner sweep (5,037 owners queued). Still to build: an independent answer key (crates.io, build-workflow users like `stellar-expert/soroban-build-workflow`, hackathon and SCF lists) to measure coverage, then forks and contributors channels.
3. Gap analysis for every "partial" tool: say concretely what is missing and PR versus new tool, with evidence. The `gaps` stage exists, keep improving it and keep `needs` evaluating from continuous discovery.
4. About 432k generic-topic repos still lack metadata or ecosystem scans; they are processed last because they rarely matter.
5. Verify the 3D graph in `web/` on a real GPU, then polish. Optional later: LLM naming of needs, GitHub Discussions, periodic refresh of active repos.

## Pipeline notes

- Autopilot `drive`: followers metadata, ecosystem, history; every 10 minutes sweep, chain, dispatch, harvest, report; every 3 hours reanalyse, mine, score, needs, gaps, graph; discovery hourly; dependents every 6 hours.
- `dispatch` plans the queue on the orphan `queue` branch and launches `extract.yml` shards when idle; `harvest` downloads artifacts, imports each file once and deletes the artifact afterwards. The `queue` branch does not exist in this repo yet, `dispatch` creates it.
- The extract workflow runs `uv run state-of-soroban extract-shard` per shard, see `.github/workflows/extract.yml`.
- Postgres is tuned in `docker-compose.yml`, check `shared_buffers` against the new machine's memory.
- Lessons: GitHub secondary rate limits hit when probing the API hard; GraphQL history totals time out in large batches; do not run heavy analytics queries while importing; the web server caches heavy aggregates on disk under `out/cache`.
