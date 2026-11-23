# Decisions

Decisions made while building, with the reason, so they can be challenged. Newest at the bottom of each section.

## Scope
- **Window is 2026-01-01 to today.** Only commits, issues, PRs and releases inside it are stored. A repo qualifies if it was pushed to in the window and contains Rust.
- **"Soroban repo" means the code uses the Soroban SDK**: a direct dependency, a `Cargo.lock` entry or a `soroban_sdk` import. Repos that only mention Soroban in text are not counted until the code confirms it.
- **Network is recorded everywhere** (mainnet, testnet). Repo signals are hints. The RPC lookup of each contract id is the truth.

## Data sources
- **GitHub search finds candidates only.** The real work (clone, history) does not touch the search limit. Two keys rotate, a third can be appended to `GITHUB_TOKENS` in `.env` and is picked up within 30 seconds without a restart.
- **Extraction uses a commits-only, sparse git fetch** (`--filter=tree:0`, sparse checkout of `.rs`, `Cargo.*`, docs and signal files). A full clone of every repo is tens of GB and the connection here does about 1 MB/s. Commit file lists are fetched only for fix commits.
- **Smallest repos first** so coverage grows fast. Huge repos go last and are skipped over 750 MB.
- **No Stellar Expert.** Mainnet contract endpoints are paywalled and the free quota is tiny. Horizon cannot serve per-contract data (it rejects contract addresses).
- **Mainnet RPC keeps about 7 days.** It is used for current state: does the contract exist, wasm hash, TTL, wasm, embedded spec and metadata.
- **Full-year on-chain history comes from the public AWS ledger lake**, summarised on GitHub Actions runners (fast datacenter link) so only a few MB come home. The workflow is built and tested on a small slice. **It is not launched in full without a go-ahead** because it spends the repo's free Actions minutes.

## Resilience
- **Everything is resumable first.** Every unit of work (search slice and page, crates.io lookup, repo, lake day) has a row in `checkpoints`. A network drop waits until online and leaves the unit pending.
- **One autopilot (`state-of-soroban drive`)** runs every stage, restarts crashed stages with backoff and follows new work as it appears. It runs under `caffeinate` so the machine does not idle-sleep.

## Proposals and the catalog
- **YAML catalog entries are seeds, not conclusions.** Real proposals are mined from the data and stored with their evidence. Seeds are scored the same way and can be marked unsupported.
- **Reuse is scored by distinct owners, not repos**, with forks removed, because copies of one template are not independent demand.
- **Exact copies and independent rewrites are scored differently.** Same body hash across repos means a template spread. Same structure with different bodies means people each wrote it, the stronger "missing macro" signal.
- **Weight goes up** for mainnet-confirmed repos, recent activity, lines removable per adopter and fix commits or issues tied to the pattern. **Weight goes down** when OpenZeppelin or the SDK already covers it.

## Interfaces
- **Live research UI** (`state-of-soroban serve`, port 8788) reads the database directly. It is the base for the later React and 3D app, which will use the same API.

## Discovery is not claimed to be complete
- **Known holes:** identical-size files can hit GitHub's 1,000-result cap inside one size bucket; code search skips most forks, non-default branches and large files; non-GitHub hosts are not searched; sibling repos of a found owner can be missed.
- **Closures built:** `Cargo.lock` and extra Stellar crate searches, crates.io dependents, an **owner sweep** that lists every repo of each confirmed owner through REST (not the search limit), a flag on search slices that hit the cap, and a capture-recapture coverage estimate on the Overview tab (shown only once text and content searches overlap on 30+ repos).
- **Still open:** non-GitHub hosts, and any repo no search or owner link reaches.

## On-chain history plan and budget (measured on a real runner)
- **Speed:** 48.8 ledgers/s per runner at 32 threads and 64 ledgers/s at 64 threads (a 2-core runner is CPU-bound). This machine does 1.7 ledgers/s, so a runner is about 30 to 40 times faster.
- **Size of the job:** mainnet 2026 is about 5.6M ledgers. At 64 ledgers/s that is about 87,500 runner-seconds, so **about 1,450 Actions minutes**, plus about 20 for job setup. Up to 20 jobs run at once, so the wall time is roughly 1.5 to 2.5 hours.
- **Budget:** the free plan gives 2,000 private Linux minutes a month. CI has used roughly 60 to 70 so far this month. The full run fits but with thin headroom. Safest is two batches: now and after the monthly reset on 1 December. Set Actions spending limit to 0 so nothing can ever bill. If it did bill, the worst case is about 10 to 15 USD (about 0.008 per minute).
- **Artifacts:** each day's summary is small (60 to 130 KB per 400 to 800 ledgers, roughly 0.5 to 2 MB per full day). A year could approach the free 500 MB artifact storage, so run in batches of 2 to 3 months, import, then delete the artifacts.
- **Not launched in full.** It needs your go-ahead. The command is `gh workflow run lake.yml -f network=mainnet -f start=2026-01-01 -f end=2026-02-28` then `gh run download` then `state-of-soroban lake-import`.

## Overnight decisions (2026-11-21)
- **Stages run as independent followers, not in sequence.** Metadata, extraction and history each loop on their own pending work, so history (issues, PRs, releases) no longer waits hours behind extraction. A periodic loop runs sweep, chain, lake import, reanalyse, mine, score, graph and report every 20 minutes.
- **The database moved onto the host disk (`./.pgdata`, git-ignored).** The Docker VM disk was 100% full (58 GB, 37 MB free) and a full disk would crash Postgres. I backed up, restored, verified every count was identical, then removed the old volume. I did not touch any other project's Docker volumes (about 12 GB of unused ones exist, they are yours to prune). A pg_dump is kept at `out/backup.dump`.
- **Contract links are ranked by evidence, not treated as equal.** The view `repo_contract_links` ranks: verified (the wasm's own `source_repo` equals the repo), deployment (id found in a deploy or config file), code, docs, fixture (tests and examples). A README mention is not proof of ownership. Today: 18 deployment, 20 code, 185 docs, 4 fixture.
- **Disk watch.** If the Docker VM disk fills again, only our own cache and volumes are safe to clear. Anything else needs the owner.

## The self-improving loop (built tonight)
- **Mined patterns become real patterns.** A helper function that 8 or more different owners wrote by hand is promoted into the `patterns` table (`origin = mined`, name-based matcher, up to 40). Extraction now uses seeds plus mined patterns.
- **New patterns apply retroactively.** Source text is stored, so the `reanalyse` stage re-matches every stored file whenever the pattern list changes (tracked by a hash on each file). No re-download needed.
- **Mined topics become search queries.** Topics carried by 15 or more confirmed Soroban repos that no query uses are auto-accepted, and discovery re-runs hourly with them. 16 were accepted on the first pass.
- **The catalog still suggests rather than rewrites.** Proposals stay `proposed` or `strong`, never silently `accepted`, because the owner should decide what counts as a proposal (`accept.policy: suggest`).
- **Dead or noisy patterns are flagged** as health candidates once there are at least 100 Soroban repos to judge against.
- **Fix evidence was tightened.** A fix commit only counts if it touches Rust and its message is not a typo, CI, lint, format, docs, changelog or version-bump change. Its weight dropped from 0.8 to 0.4, and up to 4 real example commits are stored per proposal so a human can judge them.
- **A report is written every 20 minutes** to `out/report.md` (served at `/report`): counts with changes since the last report, stage health, failed units, top proposals, what the miner found, disk and database size.
- **Disk guard:** extraction pauses below 3 GB free instead of crashing.

## Tooling needs for RFPs (new core goal)
- **The goal widened from "Rust macros" to "tooling the Stellar ecosystem needs".** Needs are first-class records (`tooling_needs`) with ranked evidence (`need_evidence`), the existing tools that partly cover them (`need_tools`, from `tool_catalog`), a demand score and an RFP draft.
- **All languages count.** An ecosystem stage fingerprints every in-scope repo (any language) through batched GraphQL file lookups, not clones: dependencies from npm, pip, Go, Cargo, Composer, Gem, pub, Swift, Gradle and Maven manifests, plus READMEs, CI workflows, scripts, Makefiles, Dockerfiles and env examples. Two phases (root listing first, then only existing subfolders) keep it at about 2 repos per second.
- **Relevance is Postgres full-text search**, indexed with GIN on issues, documents and repo descriptions, ranked with `ts_rank_cd`. It matches meaning through stemming and phrases, needs no extra service, and is fast enough to rerun every cycle.
- **Seeds are hypotheses, like the proposals.** 41 seed themes and 38 tools live in YAML. Mined themes come from the data.
- **Store everything useful.** Every matched evidence row keeps its relevance, snippet and link so the data can be reused for other purposes later.

## How tooling needs are scored (calibrated tonight)
- **Weighted search index.** Titles and file paths are weighted far above body text in the full-text index, so a match in a title counts as strong evidence and a body-only mention as weak.
- **Thresholds on relevance.** Issues need a rank of 0.3 or more and documents 0.25 or more to count (both in the YAML). Measured on a broad query: 1,087 issues matched somewhere, 412 at 0.2 or above, 271 at 0.3 or above.
- **Pain evidence is separate from topical evidence.** A topical match only says people work on the area. Pain means the issue also uses real problem or request language (missing, no way, cannot, workaround, how to, boilerplate, manually…). Generic words like add, support, feature and implement were removed from that list after they matched nearly everything, and conventional-commit titles (`feat:`, `chore:`) are excluded because many repos use them as bounty tasks.
- **Each signal is a percentile among all needs**, then weighted (pain 1.2, official repos 0.7, custom implementations 0.7, relevance 0.6, owners 0.5, engagement 0.5, recency 0.4, covered by existing tools minus 0.6). Percentiles spread the scale and recalibrate themselves as the data grows. Weights are in the YAML.
- **Specificity penalty.** A query that matches more than 20% of all issues is generic and its score is scaled down.
- **Known limit:** the corpus is hackathon-heavy, so product-domain themes (NFT, gaming, RWA) rank high on pain volume. That is demand for those apps, not necessarily for tooling. Treat the score as a ranked shortlist, and read the evidence before drafting an RFP.
- **Reactions are now stored on issues** as an engagement signal. Existing issues will get them when history is re-run with `--force`.

## Mistake and fix: ledger days
- I assumed a ledger every 5 seconds (17,280 a day). Mainnet averages about 5.8 seconds (about 15,000 a day), so the importer rejected every day as partial and then deleted the artifacts of batch 1. Fixed: the partial-day threshold is 10,000 ledgers, and artifacts are only deleted when days were actually imported. Batch 1 was re-run.

## Open for the owner
- Approve the full-year on-chain run on GitHub Actions (or choose an AWS spot VM or BigQuery instead).
- Add the third GitHub token to `.env`.

## UI speed (2026-11-22)
- The overview took over two minutes cold because counts, top edges, patterns and top contracts scan millions of rows. The api now runs the queries in parallel, serves a cached snapshot (refreshed in the background every 120 s, warmed at startup) and uses planner estimates for the four biggest row counts. Cached responses take about 10 ms. A cold start after a restart still takes about 35 s once.
- Mainnet ledger days for the whole window are imported (324 days to 2026-11-20). Launched testnet for the same window and mainnet for 2026-11-21.

## Extraction on actions runners (2026-11-22)
- Local clone and parse ran at about 400 repos an hour on a 1 MB/s link, so 21k queued repos meant 53 hours. Runners have a fast link, so clone and parse moved there.
- `extract-plan` publishes the todo list and the active patterns (seeds plus mined) to an orphan `queue` branch. The `extract` workflow splits the list into shards (index mod count so every shard gets a mix of sizes), each job clones and analyses its slice with the same code as the local stage and uploads one jsonl.gz of pydantic Analysis records.
- The `harvest` stage (autopilot) downloads finished runs, stores each analysis with the same `store` function as the local stage, records clone failures as checkpoints, then deletes artifacts. Artifacts are only deleted after a successful import.
- The local extract stage keeps running; both write through the same idempotent clear-and-insert, so overlap only wastes work.

## The public web app (2026-11-22)
- **One wrapped page, not a multi-page app.** `web/` is a React 19, TypeScript and Vite single page told as a story: hero numbers, what developers hand-write, tooling gaps with RFP drafts, mainnet vs testnet over the year, and the 3D graph as the centrepiece. Detail opens in in-page drawers and the cmd+k palette. State lives in the URL (`?proposal=`, `?need=`, `?repo=`, `?contract=`, `?node=`, `?g=chain`, filters). No router.
- **It is a separate surface from the old html UI.** `src/state_of_soroban/ui/index.html` and the `/api/overview`, `/api/graph` routes are untouched and stay for internal checks (coverage, queue health, stage runs). The new app is served at `/app` from `web/dist` and leaves those internals out.
- **Nothing is deleted or hidden in the database.** Relevance is applied only in the v2 queries: Soroban repos (`is_soroban`) and Stellar-ecosystem repos (`is_stellar`) are searchable, the 300k discovered repos never are, and the graph is capped to the top N by reuse score.
- **Types are generated, never hand-written.** `state-of-soroban openapi` dumps the schema from `create_app()` into `web/openapi.json`; `pnpm types` runs openapi-typescript into `web/src/lib/api-schema.ts`. Every v2 route has a pydantic `response_model`; the fetch layer (openapi-fetch) and TanStack Query hooks use only those types. CI regenerates both and fails on a diff.
- **Heavy aggregates are snapshots, not live queries.** The full-table scans (busiest contracts and call edges over 2M and 4M rows, pattern counts over 5M rows) took 18 to 39 s on the busy database, so they are computed in the background, cached for 30 minutes (stale while revalidate) and warmed at startup. Endpoints answer `warming: true` for the first seconds and the page polls. Repo search runs over a cached in-memory index of the 10k Soroban and Stellar repos instead of scanning the 300k table. Everything else is a primary-key or index lookup behind a 60 s cache.
- **The graph server returns the top N, the browser lays it out.** `/api/v2/graph` selects proposals, libraries and bug classes always, then repos by summed reuse score and the contracts they deploy, up to `limit` (default 900, max 4000). Neighbourhoods expand on demand through `/api/v2/neighbours`. Layout is d3-force-3d in a web worker (about 55 ms per tick at 4,000 nodes and 14,000 edges, off the main thread). Rendering is one instanced mesh per node kind with per-instance colour, one line-segment buffer for edges, labels only for the focused node and its neighbours, and bloom limited to the highlighted nodes. The 2D canvas fallback is used without WebGL or by choice.
- **The only write the app does is a note** on a repo, proposal or need, into the existing `comments` table.
- **Packages over hand-rolled code**: base-ui (drawer, tabs, tooltip, slider), cmdk, recharts, prism-react-renderer, react-markdown, motion, TanStack Query and Table, moment. Design tokens come from hackproof and live only in `web/src/styles/_tokens.scss`. Storybook (`pnpm storybook`) holds the primitives and sections.
- **Known gap:** the time scrubber filters repos by last push, not contracts by deploy date, because the data has no per-contract deployment day.
- The `dispatch` stage keeps extraction self-driving: when no extract run is active, every finished run is imported, and at least 200 repos are waiting, it publishes the queue and launches the workflow (about 250 repos per shard, 100 shards at most). The local clone follower was removed from the autopilot because it competed with artifact downloads for the one slow link.
- Harvest downloads artifacts one at a time and skips ones already on disk, so a dropped connection resumes.

## Split from soroban-wrapped (2026-11-23)

- The GitHub indexer, discovery, extraction, ecosystem graph, needs and gap analysis moved here. soroban-wrapped keeps only the on-chain ledger lake, its Actions runners and a metrics-only web app.
- The database is an exact filesystem clone of the original cluster (role and database stay `soroban`), published on host port 5443. It keeps copies of the chain tables because repo linking and the graph use them.
- The ledger lake stage, CLI commands and workflow were removed here. The Actions helpers they shared with dispatch and harvest moved to `stages/gh.py`.
- Ports differ from soroban-wrapped so both can run on one machine: api 8788, vite 5174, storybook 6007.
- Created but not started. No indexing has run since the split.
