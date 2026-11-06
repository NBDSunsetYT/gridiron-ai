# V24 dynamic and specialized-model research checkpoint

Checkpoint: 2026-11-06T07:14:04.235119+00:00. Branch: `research/dynamic-v24`. Production promotions and production data writes: **0**.

The bounded research batch is complete. No unattended process remains active. Strict pregame forecasting and strict live replay remain blocked; no claim of overall predictive superiority is established. Numerical repairs and mechanics checks do not unlock those gates.

## Scope and evidence

| League | New point-validation games | Supported marginal heads | Candidate/window evaluations | Sequential windows |
|---|---:|---:|---:|---|
| NFL | 126 | 12 | 588 | [40, 40] |
| CFB | 160 | 11 | 532 | [40, 40] |
| NBA | 80 | 15 | 388 | [40, 40] |

These are corrected-history conditional diagnostics, not publication-complete pregame forecasts. Selection excludes the 79 sealed final-test games, locked confirmations, and previously examined validation games. Training uses earlier dates and an internal distribution-calibration split. Final-test outcomes were not opened. Historical edition/arrival timestamps remain incomplete.

## A/B/C next-event comparisons

A is the unchanged V23 prior-only play-selection pool for football actions. Where V23 has no next-event API, A is explicitly an empirical prior-only reference. B adds game-state/workload features; C adds lagged outcomes and nonlinear workload. Fixed regularization is used throughout. A numerical audit found iteration-limited fits; revision r4 uses the identical objective/data with a 2,000-iteration ceiling and rejects unconverged fits. Older results are retained.

| League/task/window | Events / games | A log loss | B log loss | C log loss | C−B adjusted paired CI |
|---|---:|---:|---:|---:|---|
| CFB/actions/1 | 5337 / 37 | 0.94243 | 0.73442 | 0.73397 | [-0.00349, 0.00244] |
| CFB/drives/1 | 946 / 40 | 0.64667 | 0.71686 | 0.72714 | [0.00085, 0.02093] |
| CFB/actions/2 | 5329 / 37 | 0.94968 | 0.72135 | 0.72260 | [-0.00458, 0.00683] |
| CFB/drives/2 | 951 / 40 | 0.64917 | 0.69659 | 0.70095 | [-0.00696, 0.01575] |
| NBA/actions/1 | 8783 / 40 | 1.19057 | 1.18353 | 1.16406 | [-0.02459, -0.01328] |
| NBA/shots/1 | 6983 / 40 | 0.68340 | 0.69599 | 0.69639 | [-0.00086, 0.00130] |
| NBA/actions/2 | 8729 / 38 | 1.19982 | 1.19367 | 1.17354 | [-0.02384, -0.01583] |
| NBA/shots/2 | 6850 / 38 | 0.68171 | 0.71001 | 0.71054 | [-0.00065, 0.00174] |
| NFL/actions/1 | 5404 / 40 | 0.80755 | 0.64429 | 0.64467 | [-0.00180, 0.00258] |
| NFL/drives/1 | 871 / 40 | 0.62447 | 0.60233 | 0.60857 | [0.00028, 0.01148] |
| NFL/actions/2 | 5266 / 40 | 0.83130 | 0.65421 | 0.65324 | [-0.00273, 0.00056] |
| NFL/drives/2 | 832 / 40 | 0.64141 | 0.62976 | 0.62900 | [-0.00657, 0.00482] |

NBA action-type improvements are predominantly nonlinear within-possession event-history effects. This is not physiological fatigue, a hot-hand effect, or demonstrated full-game score/win accuracy. Shot-success complexity did not generalize. Football incremental momentum effects did not pass repeated-window checks; CFB drive scoring regressed. No arbitrary bonus was introduced.

## Specialized models

The catalogue contains 48 league/statistic heads. Models include rolling/EWMA, opponent ridge, Lasso/Elastic Net, regularized hierarchical player effects, gradient boosting, quantile medians, negative-binomial/hurdle laws, residual mixtures, empirical Bayes, opportunity×efficiency, and an inner-calibration-weighted ensemble. The first window selects the family and the next window confirms it. No verified historical prop thresholds were acquired; line-specific calibration and betting outcomes remain ungraded.

| Category | Fixed family / estimand | Earlier MAE baseline → candidate | Confirmation MAE baseline → candidate | Decision |
|---|---|---:|---:|---|
| CFB passingYards | rolling5 / conditional_mean | 50.0871 → 50.0871 | 52.3842 → 52.3842 | not established |
| CFB receivingTouchdowns | quantile / conditional_median | 0.3842 → 0.2738 | 0.3251 → 0.2207 | conditional point candidate |
| NBA rebounds | quantile / conditional_median | 1.9879 → 1.9050 | 1.9704 → 1.9251 | not established |
| NFL passingYards | hurdle / conditional_mean | 56.3531 → 55.4441 | 43.0527 → 41.8047 | not established |
| NFL receivingTouchdowns | quantile / conditional_median | 0.2533 → 0.1598 | 0.2395 → 0.1455 | conditional point candidate |
| NFL rushingTouchdowns | quantile / conditional_median | 0.2138 → 0.1415 | 0.1962 → 0.1412 | conditional point candidate |

Touchdown median heads reduce MAE relative to rolling means, which is a loss/estimand distinction, not proof of superior expected values or touchdown probabilities. Legacy frozen quantile arrays named `mean` are explicitly interpreted as medians; their values are preserved. Probability champions and joint-game replacement remain withheld. One coordinate-descent screening fit emitted a convergence warning; it was not selected for promotion. The complete 48-head leaderboard, observations, RMSE, bias, CRPS, interval coverage, zero-event calibration, paired intervals and unavailable categories are in `dynamic-v24-results.json`.

## Mechanical and live work

56 ABC/ablation complete-game mechanical trials and 24 historical-prefix continuation trials passed joint accounting checks. These are deliberately small Mode A tests with final-conditioned source/roster rates, not forecasting backtests or requested 10,000-game accuracy runs. The continuation retains actual score/statistics and simulates only remaining time. NFL/CFB shared completed-pass and rushing credits reconcile; NBA points/minute/shot/rebound budgets reconcile. A tested NBA rebound actor-shadowing defect was fixed without changing prior V23 source.

Live infrastructure implements source ordering, idempotent duplicates, revisions, gap/latency freezes, immutable snapshots, a bounded local SQLite outbox, fencing leases, quotas, exponential retries and real worker deadlines. No qualified live provider job was queued. There are zero strict live calibration/latency observations, so those metrics are unavailable.

## Evidence and remaining blockers

15 newly recovered official NBA injury facts and primary NFL/college availability source inventories were saved with publication/retrieval metadata. They do not establish full pregame starting lineups or participation coverage. Unknown availability never becomes healthy by default. NBA forward lineups after period boundaries remain incomplete; two corrected-order games were withheld. CFB administrative clock/runoff and pace certification remain incomplete. No full-game gate was bypassed, and protected pause/checkpoint files remain unchanged.

## Verification and resources

- Full Python suite: 435 passed. Subsequent V24/V23 focused regression suite: 77 passed after worker, feedback and numerical-gate changes.
- JavaScript: 793 tests in 115 files passed. TypeScript passed. Next.js production build passed; research flag-off returns HTTP 404.
- Six Chromium iPhone-size/desktop league checks passed with no page exceptions, horizontal overflow or API calls. Physical iPhone/PWA installation was not performed.
- Research dashboard reads compact frozen aggregates. It neither schedules simulations nor reads private financial data.

Controlled V24 jobs consumed 723.040 measured CPU seconds including failed attempts. Local production build separately used 100.186 CPU seconds / 60.048 wall seconds, peak RSS 1,502,756 KiB; this is not Render runtime memory. Supervised session elapsed at checkpoint: 3187.7 seconds. Cumulative budget reservations are preserved in the inherited ledger; no claim of execution while inactive.

Charts, screenshots, model pickles, forecast summaries, source receipts, random seeds, dependencies and checksums are retained under `artifacts/dynamic-v24`; raw licensed data and private records are excluded from Git. All 6,526 inherited checkpoint files passed checksum verification. Exact fitting replay requires the recorded source editions/dependencies; some earlier protocol hashes precede reporting-only code corrections, so use the preserved fitted-model hashes for forecast replay.

## Resume and decision

Do not repeat completed experiments or reopen sealed outcomes. `OPENBLAS_NUM_THREADS=1 python scripts/sequential-dynamic-v24.py` returns the completed r4 receipt. New evidence/numerical revisions require a new immutable protocol rather than modifying frozen snapshots. `python scripts/analyze-dynamic-v24.py`, `python scripts/dashboard-dynamic-v24.py`, and `python scripts/plots-dynamic-v24.py` reproduce summaries. `GRIDIRON_RESEARCH_V24=1 npm run dev -- --port 3024` previews the cached research-only route `/research/v24`.

No production model qualifies for automatic promotion. Next phase is isolated Render application compatibility/migration based on the unchanged production branch, with no DNS or traffic switch.
