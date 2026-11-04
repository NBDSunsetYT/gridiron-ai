# GRIDIRON AI engine overhaul and NBA research

This release extends the existing application. It does not replace the database, reset user records, change paid plans, or claim that an unvalidated model is accurate.

## Confirmed original defects

The preserved Ohio State–USC October 31, 2026 input artifact was replayed for 10,000 games with its original seed. All eight checked distributions, accounting/tempo outputs, correlations and representative traces matched exactly. File checksums remain unchanged. See `reports/v15-original-run-diagnostic.json`.

1. **Historical participation was used as current personnel.** Historical quarterback identities were sampled with plays. Ohio State's input contained 166 Sayin attempts versus 12 Fahey attempts; there was no current-starter allocation step. This explains a major allocation error without using the final box score to tune it.
2. **Reported absences were not propagated.** The saved run still gave a reported-out quarterback opportunities. The fitted inputs contained no availability-labeled training observations. A generic injury banner was not an injury-adjusted model.
3. **Clock evidence was unsuitable for full-game tempo.** The source adapter used recorded play-duration deltas with many zero values and omitted much between-snap runoff. The original run averaged **207.5782 plays per complete game**. Large team passing volume and concentrated targets compounded individual-yardage inflation.
4. **Opponent-conditioned samples did not validate whole-game behavior.** Per-play statistical fit was not evidence of calibrated game scores, player opportunities or distributions. Uncertainty and current-lineup checks were incomplete.

The diagnostic identifies confirmed structural defects. It does not attribute every yard of each individual error to a proven causal factor. The original forecasts and postgame comparisons have not been replaced.

## Football candidate

`modeling/football_data_v15.py` separates NFL and NCAA data, uses observed snap-to-next-snap clocks, handles supported standalone penalties, and keeps final results outside fitted observations. Whole games crossing a training cutoff are excluded.

`modeling/football_v15.py` is an original vectorized possession/state model. Regularized play-choice/dropback models, offense/defense/player terms, field-dependent touchdown hurdle models, conditional yard residuals and observed clock distributions govern shared plays. Current quarterback and availability assumptions are allocated before outcomes. Passing completions/yards and receiver receptions/yards reconcile within every simulated game. NCAA sack accounting is separate from NFL accounting. Historical opportunity redistribution is a conditional scenario, not a validated causal injury estimate.

The production default is **not switched** to a candidate simply because it completes simulations. The new model is available through the authenticated private candidate inference boundary and offline audit. Existing engines remain available; a new game-wide integrity guard withholds archived evidence when a currently reported-out player still receives opportunities or complete passing/receiving accounting fails.

The first candidate was worse than the simple development baseline. Its exact source is preserved in `football_v15_baseline.py`. The later touchdown-hurdle candidate is reported separately. No full-game model has been promoted on these results.

## Separate NBA engine

`modeling/nba_v15.py` fits NBA-only box scores and play-by-play free-throw trips/substitution intervals. It models possessions, quarter boundaries, overtime, five-player rotations, observed minute budgets, shots, free throws, rebounds, assists, turnovers, steals, blocks and fouls. Player points equal team scores and player minutes equal five players' game time in every run. PRA, PR, PA, RA, double-doubles and triple-doubles derive from the same outcomes.

The NBA navigation offers games, PropLine sportsbook-reference quotes, backend simulations, player distributions, model performance and authenticated saved references. Counts are 10,000 by default, with 50,000 and 100,000 available. Public navigation itself does not launch expensive simulations. Current lineups and injury coverage are explicitly unverified when not supplied by a verified source. Raw probabilities are never relabeled as calibrated.

NBA source preparation is shared for six hours, with bounded fixed-source downloads and a distributed lease. Simulation keys include exact event/team identity, model/data version, material availability and count. Observation timestamps alone do not invalidate a result. Prepared artifacts are approximately 390 KB, rather than the early untrimmed 19 MB artifact. Simulation summaries use content-addressed compressed objects and small persistent references. No full simulated plays are permanently stored.

Known limitations include technical/bonus administration, team rebounds, causal rest/back-to-back/blowout effects and validated injury/lineup effects. NBA contract combinations requiring unavailable joint settlement rules remain unsupported. Separate NBA market-model blending is not fitted without verified historical lines and chronological validation.

## Historical evaluation protocol

The seeded selection includes 500 distinct football games from 2024 and 2025 and 40 NBA games from 2025. Every evaluated forecast uses 10,000 complete games. Forecast distributions and model/code checksums are written before final-stat retrieval. Development and validation are separate; final-test parameters **and roster features** are frozen before the final period (football November 15, 2025; NBA April 1, 2025). No earlier final-test result enters a later final-test fit. Frozen rosters can become stale; that limitation is intentional and reported.

Original historical publication timestamps, complete injury/lineup archives and correction availability cannot be established. Therefore **zero games qualify as fully verified prospective pregame tests**. These are event-chronological retrospective audits. Only exact identity-matched player statistics are graded; missing participants are not silently assigned zero. Historical prop thresholds, prices and settlement terms were unavailable, so no over/under win rate or market advantage is fabricated.

`reports/v15-validation.json` contains per-version, per-league and per-phase MAE, RMSE, median error, bias, Brier score, log loss, total/margin errors, 90% player interval coverage, identity coverage, raw calibration bins, 2,000-replicate week-block bootstrap intervals, failures and the exact game inventory. `reports/v15-calibration.png` is the exportable calibration plot. Repeated development games do not inflate the unique-game count.

## Data, infrastructure and security

- GitHub: `NBDSunsetYT/gridiron-ai`, with pre-upgrade checkpoint and versioned changes.
- Vercel: existing Next.js frontend plus private Python quant service. **Simulations run on this private Vercel service.**
- Render: existing free PropLine data gateway; it does not run the simulation model. The gateway adds documented NBA categories while preserving NFL/CFB routes, quotas and caching. No provider key was moved to Vercel or the browser.
- Supabase: existing `qdtdjbapdipopncklsdb`. Existing owner-RLS records hold private NBA references; shared compressed research uses existing storage. No schema migration, duplicate table or financial-record modification is required.
- NBA historical sources: sportsdataverse's published ESPN NBA box-score/play-by-play releases; upcoming schedules: ESPN's published NBA scoreboard. These are timestamped source observations, not a licensed live lineup guarantee.
- PropLine: sportsbook reference only. DraftKings Sportsbook is separate from DraftKings Predictions. NBA categories are limited to officially documented provider endpoints. Access and player crosswalks must be verified in actual production responses.
- MongoDB/R2: existing optional adapters are preserved; no new credentials/resources were provisioned. Where unavailable, no cloud archive or recovery capability is claimed.
- OpenAI: NBA stored-data retrieval tools were added. Missing OpenAI credentials still block genuine live LLM generation; deterministic application calculations are not described as a live AI response.

## Reproducibility and local commands

Install Node dependencies with `npm ci`, and Python dependencies with `pip install -r modeling/requirements.txt`. Configure existing server-side environment variables using `.env.example`. Never commit `.env.local`.

Run `npm run dev:full` for the local app/worker, `npm test`, `npm run test:python`, `npm run test:postgres`, `npm run test:e2e`, and `npm run build`. Install optional research dependencies with `pip install -r modeling/requirements-research.txt`, then run `python scripts/download-engine-v15-data.py` to verify/download the exact source checksums. Historical audit scripts use these public Parquet files under `/tmp`; do not unpickle an uploaded/untrusted cache. Frozen selection files and compressed runs stay under ignored `artifacts/engine-v15/`.

Run `scripts/backtest-engine-v15.py --phase development --candidate baseline`, then the `hurdle` validation/test phases. NBA uses `scripts/backtest-nba-v15.py`. `scripts/report-engines-v15.py` aggregates without fitting or editing original forecasts. `scripts/benchmark-engines-v15.py` verifies scale, histogram mass, accounting and exact seeded repeats. Exact replay requires identical input/model/code/dependencies, NumPy RNG and batching; changing the batch size changes random-number allocation.

## Installation and rollback

Open the existing HTTPS app in iPhone Safari, choose **Share → Add to Home Screen → Add**. The manifest/icons/standalone mode, safe areas and private-data caching protections are preserved. Desktop/Chromium iPhone viewport tests are not physical iPhone installation tests.

Rollback uses the previous Vercel deployment; Render's previous gateway commit is retained. No database rollback/reset is needed. Unpromoted candidate source, rejected experiments and immutable historical forecasts remain available for investigation.

## Measured final-period results

| League | Distinct test games | Candidate score MAE | Simple baseline MAE | Candidate minus baseline 95% interval |
|---|---:|---:|---:|---|
| CFB | 100 | 16.675 | 9.748 | 6.146 to 7.423 |
| NBA | 20 | 10.371 | 11.800 | -3.686 to -0.377 |
| NFL | 50 | 8.180 | 7.382 | -0.262 to 1.825 |

The audit evaluated **500 distinct football games and 40 distinct NBA games**, with 570 frozen forecasts totaling 5,700,000 complete simulated games across candidate versions. Repeated development games are counted once as games. No final-stat retrieval failures were recorded. NFL and CFB candidate score errors do not justify promotion. NBA’s lower error on 20 test games is an observed small-sample retrospective comparison, not evidence of reliable current player-prop accuracy or a validated injury-adjusted improvement. All new models remain unpromoted.

### Scale and compute

Real-history 10,000-, 50,000- and 100,000-game runs passed NFL, CFB and NBA accounting/histogram checks. Same-seed replays matched exact distribution checksums. A local mathematically equivalent array-conversion optimization reduced the measured 1,000-game CFB workload from 6.977 to 1.756 CPU seconds (74.8%), with identical checked outputs. This is not a measured reduction in the hosting bill.

At 100,000 games the NBA summary occupied 37,813 compressed bytes and the benchmark process peak RSS stayed below 194 MB. Full-run plays were not persisted. Current NBA model and result caching reuses data across visitors and reloads.

### Tests and release verification

Baseline: 753 TypeScript and 200 Python tests passed. Updated unit, integration, browser, production and deployment evidence is recorded in `reports/v15-release-verification.json` after completion. Real-source public NBA reopen tests use existing Supabase records and perform no financial writes. Local ledger/browser fixtures are isolated and labeled. Physical iPhone installation and live OpenAI generation are not claimed.


## Verified live market access

The staged production API returned HTTP200 from PropLine: 12,893 current NBA sportsbook-reference quotes, including 1,816 DraftKings Sportsbook quotes. Current category counts were points2,916; rebounds2,714; assists1,848; three-pointers2,002; steals776; blocks380; PRA1,724; double-doubles533; turnovers0. Other bookmaker counts were FanDuel1,772, BetMGM976 and Hard Rock8,329. Counts change with market availability; this is a timestamped test, not a guarantee of execution.

The documented NBA `/ids` endpoint returned NBA-native team IDs and null ESPN event IDs in the inspected current response. Quote player IDs were NBA-native (`nba:…`), while the historical model uses exact ESPN IDs. No verified crosswalk was established. Exact NBA quote-to-model comparisons therefore remain withheld. The UI distinguishes this identity issue from a provider outage; no fuzzy name-only match or invented contract is substituted. A public ESPN athlete response confirmed its ESPN ID; the inspected NBA CDN roster source returned403 and was not bypassed.

New NBA runs retain the immutable signed fitted-input object reference, configuration, seed and code version. Earlier local test runs without that new reference remain archived unchanged. Public archive links reopen saved distributions without another Monte Carlo run.

Independent NBA player-threshold research remains available through the saved-distribution chart: select a player/statistic, enter a clearly labeled hypothetical threshold and choose over/under. Counts, K/N, Wilson95% sampling intervals, standard errors and pushes come directly from the coherent game distribution. This does not invent a market, imply a current quote, or bypass the missing provider crosswalk.

## Production release

Live: https://gridiron-ai-gray.vercel.app. Tested code commit `d85034a662d39638064c66a357971591db27eb15`; Vercel deployment `dpl_2TDamrZokxhF7q3LdrgHQ6Gb5ztE` is READY and assigned to the live alias. Render gateway commit `4049df71289fe697e5bd90f5e3ee1c06cbec8750` is live on the existing free service. Vercel Git-source access was unavailable, so authenticated source uploads were used without changing the project or disabling protection.

Passed: 768 TypeScript tests, 218 Python tests, all13 local PostgreSQL/RLS/ledger/cache/learning regression scripts, 78 existing-flow browser checks on a production build, and all8 live production NBA browser checks across desktop and iPhone-sized Chromium. The actual production NBA workflow completed10,000 games in36.3seconds and restored exact distributions on a separate request in1.7seconds. These are observed end-to-end latencies, not isolated CPU benchmarks or promises for future runs.

Production Supabase owner policies and the existing record constraints support the new private reference type; financial-table row hashes were unchanged. No schema migration/reset occurred. New shared NBA research survived process changes, reloads and separate requests. A real authenticated private NBA save across accounts was not executed because isolated confirmed QA credentials were unavailable.

All8 production browser tests passed after making transport-sensitive requests through the browser; the initial API-only Playwright context could not traverse the environment proxy. An earlier local trace-output collision was corrected with separate artifact directories. The final test results are not fabricated or inferred from those failed attempts.

### Remaining work

The replacement football candidate requires further development and a new untouched evaluation period. NBA exact market identity linkage, verified lineups/causal injury adjustments, automated NBA postgame learning and durable background orchestration remain incomplete. Large live serverless runs may exceed duration limits;100,000-game production execution is not claimed. Live OpenAI generation needs a server credential. MongoDB/R2 application credentials remain unconfigured. Physical iPhone installation and authenticated NBA private save across production accounts remain unverified.

The source ZIP and compact historical forecast export are in `artifacts/`. The compact export contains forecast distributions and evaluation summaries, without raw play-by-play caches or millions of simulated plays. Frozen game selection, source checksums, runtime manifest and aggregate metrics are committed to GitHub. See `reports/v15-release-verification.json` and `reports/v15-production-public.json` for machine-readable verification.

The full changed-file inventory is `reports/v15-files-changed.json`. Actual production screenshots are in `docs/screenshots/v15-nba-desktop-chromium.png`, `v15-nba-iphone-chromium.png`, `v15-production-markets.png` and `v15-production-validation.png`.
