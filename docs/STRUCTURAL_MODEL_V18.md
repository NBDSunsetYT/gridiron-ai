# Structural model experiment v18 — 4 November 2026

Measured projection gains were found against rolling baselines. A general improvement over the existing full-game reference was **not** established. No model was promoted or connected to production.

## Diagnosis of the 342 exposed development games

- NFL: 124 games; CFB: 174; NBA: 44. The audit now separates informative player opportunities from irrelevant all-zero rows. It includes season, available position, player, statistic, model-favorite/underdog, volume and available pace breakdowns. Unknown injuries and positions remain unknown.
- NBA discarded 2,077 of 5,273 complete team box scores (39.4%) because free-throw trip evidence was incomplete. The same filter then controlled rotation and player-efficiency histories. The stricter pace cohort still needs verified trip evidence; usable player boxes do not. The legacy possession formula remains approximate for and-ones and technical/bonus administration.
- On the later NBA development sample, this coupling lost an average 1.40 days and up to 8.96 days of otherwise usable team rotation evidence. Evaluating only actual participants hid workload errors: the zero-inclusive complete-box audit gives 8.78 minute MAE across 564 forecast player-games in 23 qualifying games.
- NBA fixed rotation budgets barely varied between simulated games. Their nominal 90% minute intervals covered only about 20% of actuals in the nine-game control. Additional Monte Carlo draws cannot repair that structural uncertainty defect.
- CFB forecasts averaged 27.53 more state transitions than accepted historical events across 150 older games. This is an accepted-record comparison, not a claim of exact total-snap error: rejected plays and source coverage limit inference.
- Receiver identity is missing on 20,077 of 110,516 normalized CFB pass plays and 1,608 of 36,233 NFL passes. An unnamed receiver is not automatically a legitimate throwaway. CFB target/route allocation cannot be treated as fully observed.
- Missing historical injury publication, snap/route shares, current roster changes and depth charts prevent an injury-specific causal diagnosis. The models must not invent those inputs.

## Actual structural changes

1. Separate NBA complete-box rotation/player-rate evidence from strict play-by-play pace evidence. Keep the possession acceptance checks intact.
2. Fit zero-inclusive opportunity projections using earlier appearances, participation, team volume and opponent allowed statistics. Future final rosters never define the candidate player pool.
3. Compare rolling averages, opponent-adjusted rolling averages, regularized Ridge, player/team random-intercept MAP shrinkage, fixed gradient boosting and opportunity × efficiency projections. The MAP model is not a full Bayesian posterior.
4. Inject learned QB/dropback, target and rushing opportunity budgets into the original football state engine. Every completion/rush still updates shared team/player outcomes. A separate allocation-only ablation retains the original QB and play-call probabilities.
5. Fit NBA expected minutes, reconcile a joint 240-minute budget, and simulate shared historical rotation plans. A sampled DNP is a workload plan, **not** a verified injury probability. Every game keeps five players on court and reconciles points, minutes and combined-stat outcomes.

The new code is offline research. Frozen v15/v16 files, current market adapters, wallet, authentication, PWA and production paths were preserved.

## New chronological validation

536 games, excluded from previously evaluated game IDs: 56 NFL, 240 CFB, 240 NBA. Three windows per league were locked before evaluation. Standalone coefficients trained before July 2025 (237 NFL, 622 CFB and 1,270 NBA eligible training games). Lagged features update from earlier completed games with an embargo. Full-game models fit before each cohort; earlier validation games may become legitimate later history.

These are retrospective validation results, **not** an untouched final test or verified originally published pregame reconstruction. The original 342 are development only. Later structural ablations reuse the nine-game simulation sample. A future final protocol is reserved from 5 November 2026, requiring pregame snapshots; it is not graded or automatically scheduled by this change.

### Player projection MAE: rolling five-game baseline → fixed Ridge

| League/statistic | Games | Players | Player-game observations | Rolling MAE | Ridge MAE | Game-clustered 95% MAE-delta interval |
|---|---:|---:|---:|---:|---:|---|
| NFL passingAttempts | 56 | 90 | 254 | 8.854 | 6.712 | [-2.884, -1.207] |
| NFL passingYards | 56 | 90 | 254 | 62.409 | 50.031 | [-17.490, -6.962] |
| NFL receivingYards | 56 | 479 | 1470 | 14.133 | 13.512 | [-0.965, -0.259] |
| NFL rushingYards | 56 | 331 | 933 | 11.131 | 10.074 | [-1.469, -0.601] |
| CFB passingAttempts | 240 | 675 | 1646 | 5.765 | 4.781 | [-1.129, -0.627] |
| CFB passingYards | 240 | 675 | 1646 | 43.209 | 40.741 | [-3.827, -0.303] |
| CFB receivingYards | 240 | 2894 | 7705 | 13.125 | 12.597 | [-0.654, -0.327] |
| CFB rushingYards | 240 | 2072 | 5331 | 13.601 | 12.244 | [-1.577, -1.153] |
| NBA minutes | 240 | 491 | 6657 | 6.810 | 6.481 | [-0.440, -0.220] |
| NBA points | 240 | 491 | 6657 | 4.834 | 4.623 | [-0.271, -0.154] |
| NBA rebounds | 240 | 491 | 6657 | 1.986 | 1.908 | [-0.099, -0.056] |
| NBA assists | 240 | 491 | 6657 | 1.276 | 1.233 | [-0.058, -0.028] |

The universe includes pregame-supported backup/low-volume players. These are not starter-only errors. No unit-mixed aggregate player MAE is reported. Confidence intervals are exploratory, unadjusted for multiple comparisons, and resample games rather than pretending correlated player rows are independent games.

### Team score and moneyline projections

| League/model | Score MAE | Brier | Log loss |
|---|---:|---:|---:|
| NFL rolling5 | 8.562 | 0.2431 | 0.6679 |
| NFL ridge | 8.033 | 0.2425 | 0.6719 |
| NFL hierarchical | 7.926 | 0.2357 | 0.6588 |
| NFL boosted | 8.159 | 0.2302 | 0.6383 |
| CFB rolling5 | 10.346 | 0.2165 | 0.6226 |
| CFB ridge | 9.446 | 0.2072 | 0.6014 |
| CFB hierarchical | 9.379 | 0.2033 | 0.5932 |
| CFB boosted | 9.688 | 0.2099 | 0.6097 |
| NBA rolling5 | 11.013 | 0.2644 | 0.7462 |
| NBA ridge | 9.815 | 0.2302 | 0.6531 |
| NBA hierarchical | 9.868 | 0.2350 | 0.6677 |
| NBA boosted | 9.922 | 0.2369 | 0.6701 |

Projection probabilities use chronological training-holdout residual distributions. They are neither Monte Carlo probabilities nor calibrated probabilities. Each statistic’s RMSE, bias, prediction-interval coverage and sample sizes are in the JSON results. These independent projections cannot substitute for coherent joint game simulations.

## Full-game structural checks

27 distinct validation games (nine per sport), 90 forecast runs and 900,000 complete simulated games. Counts remain 10,000 per run. No trial-count sweep was used to manufacture accuracy. All runs passed the shared accounting and distribution-mass checks.

| League/candidate | Games | Team-score MAE | Brier | Log loss |
|---|---:|---:|---:|---:|
| CFB allocation_only | 9 | 11.368 | 0.2016 | 0.5746 |
| CFB frozen_v15 | 9 | 11.355 | 0.2086 | 0.5937 |
| CFB learned_allocation | 9 | 11.672 | 0.2096 | 0.5964 |
| NBA box_coverage | 9 | 11.267 | 0.2364 | 0.6703 |
| NBA frozen_v15 | 9 | 10.853 | 0.2501 | 0.7005 |
| NBA learned_minutes | 9 | 11.119 | 0.2329 | 0.6642 |
| NBA rotation_bootstrap | 9 | 11.131 | 0.2347 | 0.6675 |
| NFL allocation_only | 9 | 8.482 | 0.3557 | 0.9432 |
| NFL frozen_v15 | 9 | 8.499 | 0.3496 | 0.9264 |
| NFL learned_allocation | 9 | 8.793 | 0.3639 | 0.9644 |

On the same 211 supported NBA player-games, control minute MAE was **7.371**, learned-minute MAE **6.600**, and shared-rotation MAE **6.616**. Nominal 90% minute interval coverage changed from **20.4%** (control), to **25.6%** (fixed learned budgets), to **76.8%** (shared rotation plans). The last change improves the uncertainty representation materially, but remains under-covered.

NFL allocation-only receiving-yard MAE improved from **18.522 to 17.609** across 143 common supported player-games. Its paired game-bootstrap interval was negative, but moneyline reliability regressed. CFB allocation-only Brier improved in the small sample; score and some player errors did not. No overall win is claimed.

Common-support comparisons and coverage gaps are explicit. NBA complete reconciled boxes permit DNP=0; missing football identities are excluded and reported. Changed QB inference is not hidden: the learned model changed one CFB inferred starter. No final box score was used to choose that starter.

## Accept/reject decisions

| Candidate | Decision and exact reason |
|---|---|
| NFL/CFB Ridge components | Retain promising opportunity/yardage components for research. Some do not improve every chronological window; NFL moneyline log loss regresses against its rolling baseline. Full-game integration fails the complete reliability gate. |
| Hierarchical MAP and gradient boosting | Retain measured category-specific evidence only; no complexity preference. Every per-category result and important-category regression is recorded. |
| Hybrid opportunity × efficiency | Research only. Some mean errors improve, but chained prediction intervals are not independently validated. |
| Football learned allocation + dropback shift | Reject production promotion: team-score and moneyline metrics regress on the paired small sample. |
| Football allocation-only ablation | Research only. NFL receiving error improves but moneyline reliability regresses; CFB results are mixed and the nine-game sample is underpowered. |
| NBA box-coverage repair | Corrects a confirmed data-coupling defect, but alone does not improve all primary errors; do not deploy an unvalidated forecast pipeline. |
| NBA learned minutes | Retain workload component for research. Mean error improves, but fixed budgets severely understate playing-time uncertainty and team-score MAE regresses. |
| NBA shared rotation plans | Retain structural variance improvement for research. Interval coverage remains below nominal 90%, team-score MAE does not improve, and genuine pregame lineup/availability coverage is missing. |

No candidate passes all predefined gates: minimum full-game sample, three reliable windows, important-category regression checks, acceptable probability reliability, and verified pregame source coverage. The JSON contains every family’s category-level retention/rejection reasons and paired uncertainty. No model was promoted or deployed.

## Resources, preservation and tests

- Instrumented model experiments: 1460.02 local CPU seconds. Cold replay: 41.33 seconds. Combined instrumented research/replay: 1501.35 seconds, below the 1,800-second research budget. Small audits, test-suite execution, startup and packaging are separately excluded from this CPU total.
- Largest **reported full-game** process RSS: 931.8 MiB. Whole experiment memory peak was not instrumented; a live projection RSS sample was 1,850,972 KiB. Do not treat the smaller full-game maximum as the whole-project maximum.
- No Vercel or Render simulation/API/background job was initiated. No paid infrastructure, new cron or production compute setting was enabled. Existing platform billing was not measured or changed.
- 41 targeted Python regressions passed; 786 TypeScript tests across 113 files passed. These are local tests, not live provider or physical-iPhone verification.
- Three independent cold-process replays of 10,000 games each reproduced score, player, margin/total distributions and convergence exactly. This is 30,000 additional verification games, not new validation games.
- Four locked source caches, 66 fitted input artifacts, 37,884 whole-game training memberships, and 14,400 NBA rotation-history memberships passed the chronology/integrity audit with zero violations. Checksums of all 342 original development summary/evaluation files verified unchanged. No financial database operation occurred. Source checkpoint and old forecasts are preserved.
- Only compact distributions, input/model snapshots, seeds, provenance and diagnostics were saved. No simulated play archive was persisted.

## Reproduce

Use the existing trusted, owned archive caches listed by SHA-256 in `docs/reports/structural-v18-protocol.json`. Do not unpickle browser uploads or untrusted files. The evidence archive retains the four public-source normalization caches and original experiment artifacts; no user financial data, credentials or service keys are included.

```bash
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
python -m unittest modeling.test_structural_v18 modeling.test_engines_v15 modeling.test_iterative_learning modeling.test_calibration_research modeling.test_compute_policy
# Prepare a NEW output directory; existing snapshots refuse overwrite.
python scripts/structural-v18.py prepare --out /tmp/gridiron-v18-reproduction --cpu-seconds 120
python scripts/structural-v18.py projections --out /tmp/gridiron-v18-reproduction --cpu-seconds 600
# Existing frozen artifacts: these commands do bounded local-only work.
python scripts/verify-structural-v18.py
python scripts/report-structural-v18.py
```

Full-game experiment runners and their CPU caps are in `scripts/backtest-structural-v18.py`, `scripts/rotation-bootstrap-v18.py`, and `scripts/allocation-ablation-v18.py`. They are not scheduled, not loaded by application request handlers, and never auto-promote. Input source checksums are checked before research. Exact seeded replay requires the recorded dependencies and categorical-order sidecars.

The stop condition was completion of the bounded, predeclared cohorts and structural hypotheses. More calibration sweeps would not solve missing authoritative lineup/injury/route evidence or the remaining score/variance trade-offs. The next defensible step is collecting original-time pregame availability/roster snapshots and validating retained components on a new prospective period, not retuning the reserved final set.
