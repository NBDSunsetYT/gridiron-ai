# GRIDIRON AI V22 — integration and independent component validation

Research branch: `research/integration-v22`, from V21. Production, hosting, billing, financial records and historical forecasts are unchanged. **No production model promoted. No newly eligible strict full-game matchups.**

## Implemented repairs

- Integrated corrected historical CFB player/team boxes into a separate full-game input artifact: 1020 earlier reconciled games, 223 supported team completion bridges. Sack/interception mass is preserved while earlier official conditional completion counts determine an intercept correction. State slopes are not tuned to final scores.
- Preserved anonymous game-level team credits and **309 unidentified passing snaps** in separate team/event provenance buckets. A final QB box total does not identify the passer on an anonymous snap. These source counters are never added to the reconciled box totals again.
- Serialized the frozen V21 interval-censored model and checked all 12 fitted timing contexts without refitting/repeating V21 experiments. Timed events cannot take zero clock charge; administrative events need separately verified timing evidence.
- Fixed double drive-start counting on scoring/possession transitions. Synthetic mechanics checks conserve each 900-second regulation quarter, 3,600 seconds total, drive starts and per-team passing/receiving totals. Active-QB kneel handling was already correct and remains so.
- Added a model-content-bound consistency certificate and unchanged strict evidence gate. NFL/NCAA timing evidence is league-specific. Model mutation, stale checksums, missing administrative timing or unsupported evidence withhold the joint forecast.
- Added CFB team-attempt budget → multinomial QB share (including an unassigned/new-player bucket) → binomial completion → regularized yards/completion model. Allocation reconciles to the team attempt budget. No guessed availability probabilities.
- Replayed the active production **source algorithm** (`observed-player-games-12.3.0` / `hierarchical-player-cdf-12.3.0`) on eligible prior NFL weekly observations. Both source files match GitHub main. This is not the rolling5 reference, a live Render artifact verification, or a recovered historical roster/injury qualification.
- Reused V21 NBA starter-state and on-court rebound models across new windows. Repaired a canonical archive-ID join that initially prevented rebound scoring. Original minute forecasts/fitted parameters were retained.
- Added bounded, resumable jobs, immutable registrations/revision receipts, exact source checksums, frozen forecasts before grading, paired game-level bootstrap comparisons and factor error diagnostics. All heavy work stayed in this local research environment.

## Independent conditional measurements

**176 distinct newly graded games**: NFL 60, CFB 44, NBA 72. There were 183 selected games; seven CFB games lacked sufficient earlier own/opponent participant history. Eight frozen windows contain **5,070 player-stat observations**. The rebound completion reuses the same 72 NBA games; it is not an additional sample.

| Comparison | Games / observations | MAE reference → candidate | RMSE reference → candidate | Paired MAE difference 95% CI |
|---|---:|---:|---:|---:|
| NFL passing yards: production-source replay → hurdle | 60 / 208 | 95.469 → 63.996 | 114.325 → 82.918 | [-40.217, -22.560] |
| CFB attempts: repaired-history hurdle → opportunity chain | 44 / 256 | 5.417 → 5.124 | 8.539 → 8.440 | [-0.499, -0.089] |
| CFB passing yards: repaired-history hurdle → opportunity chain | 44 / 256 | 44.378 → 41.253 | 67.789 → 65.927 | [-4.890, -1.228] |
| NBA minutes: hurdle → starter-state | 72 / 2033 | 6.252 → 6.110 | 8.367 → 8.272 | [-0.196, -0.089] |
| NBA rebounds: hurdle → identified-court model | 72 / 2033 | 1.894 → 1.904 | 2.664 → 2.655 | [-0.033, 0.050] |

Intervals use 2,000 paired **game-clustered** bootstrap draws. They are nominal descriptive intervals, not familywise-adjusted proof of production superiority; recurring players/teams can create additional temporal dependence.

NFL validation windows: October, November and December 2023 (20 games each), with 2022/earlier-2023 training history. CFB: September/October 2025 (14/30 eligible games), using corrected earlier counts. NBA: February 2025, November 2025 and January 2026 (24 each), spanning two seasons. The hypotheses/parameters/selection were frozen before this batch's grading. These are new conditional validation samples, **not a new untouched final test** or strictly reconstructed pregame forecasts.

### Important limits and decisions

- **NFL:** retain hurdle as a research candidate. Broad conditional MAE improved against the production-source distribution expectation, but missing historical roster/injury gating makes this an incomplete comparison with the actual production pipeline. For QBs with prior mean ≥25 attempts, the MAE difference is **−3.229 yards, CI [−12.526, 4.817]** over 58 games/91 observations: high-volume superiority is not established. No production/full-game champion replacement.
- **CFB:** retain the opportunity chain for further research. Direction improved in both windows, but September's passing CI crosses zero. Prior ≥25-attempt quarterbacks: **−6.450 yards, CI [−13.486, 0.966]**, 29 games/44 observations; no established high-volume improvement. The box-accounting repair and the new structural head are distinct changes; this experiment measures the head against already repaired inputs, not a claim about end-to-end full-game accuracy.
- **NBA minutes:** retain as a research candidate; all three windows improved in direction, but November's CI narrowly includes zero. Upcoming starting lineups remain uncertain, not final starters retroactively supplied to the model.
- **NBA rebounds:** reject both the identified-court and minutes-proxy challengers as improvements. Aggregate rebound MAE worsened slightly, and every window's CI crosses zero. Better minutes alone did not establish a better rebound forecast.
- **Moneyline Brier/log loss, team-score MAE, prediction-interval coverage and calibrated contract probabilities:** **not measured in V22** because no new joint forecast passed the strict evidence/consistency requirements. Point-head averages are not probability distributions. No historical betting thresholds or market prices were fabricated.

## Error attribution and remaining blockers

CFB four-factor product-error attribution is defined on 107 positive-attempt/completion QB appearances. Mean absolute algebraic contributions: QB opportunity share **51.46 yards**, team passing volume **35.97**, yards/completion **32.00**, completion efficiency **20.40**. Components can cancel and are not percentages or causal injury effects. Zero-opportunity rows have undefined efficiency factors and are reported separately. The largest remaining structural weakness is identifying who receives the passing workload; it cannot be solved by assigning anonymous snaps to a guessed starter.

Strict full-game blockers remain: independently verified historical play/possession realism; NCAA live-ball versus between-action runoff and two-minute-warning state; administrative timing; overtime distribution/accounting validation; targets and sack/dropback coverage; versioned pregame lineup/availability/participation/weather evidence; quantified model uncertainty. The certificate explicitly leaves these unresolved. Mechanical conservation does not establish realistic full-game distributions.

## Evidence coverage

Recovered **44 NFL injury facts across four selected games**, plus **16 NBA injury facts across two games**; **51 of 60** identities resolved. These are official publisher-dated/versioned reports, not independently captured archival snapshots. One ambiguous NFL list line was rejected rather than guessed. Official NBA PDFs were fetched and parsed using the documented historical filename variants.

CFB: three primary-source pages inventoried; **zero new accepted timestamp-qualified availability facts**. The dated Tennessee preview/American availability page did not provide a verifiable canonical publication/version timestamp through the available responses; the SEC archive did not supply a recoverable event-level report timestamp. URL dates and current retrieval times were not substituted for publication evidence.

**Zero complete pregame starting lineups and zero fully covered strict pregame games.** Missing players remain unknown. New evidence is stored separately and was not retroactively inserted into frozen forecasts.

## Integrity and execution

- 5917 inherited V20/V21 artifact checksums verified; all original pauses/checkpoints preserved.
- **79 sealed final games + 82 locked confirmation games excluded** from candidate training and forecast cohorts. Protected overlap: zero. No final cohort graded.
- Full Python suite: **360 passed**, exit 0; final focused V22 suite: **10 passed**. Final focused run includes the additional league-specific timing guard. Suites overlap; counts are not additive.
- Full-suite CPU: **170.50s**, wall 170.56s. Bounded research jobs including failed attempts: **254.48 CPU seconds**; peak **1.27 GiB RSS**. These are measured windows, not an invented total for uninstrumented setup. The inherited 10-hour cumulative ledger/reservations were retained.
- One initial component job was interrupted after detecting a protected-manifest read inside a raw-row loop; the invariant was hoisted without changing exclusions or prediction arithmetic. Rebound archive lookup and robust visible NFL article-list parsing were separately versioned repairs. Failed receipts remain available.
- Frontend/mobile/deployed services were not retested or changed. No Vercel/Render workloads, cloud deployments, paid resources or production database writes were initiated.

## Reproduce and resume

Restore the existing private V20/V21 checkpoint dependencies and `artifacts/integration-v22` checkpoint; raw archives/models are intentionally not published to the public Git repository. Preserve all original source hashes. Source acquisition URLs/checksums, selection, fit cutoffs, fixed seeds, numeric code versions, models and frozen forecasts are included in checkpoint manifests.

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python scripts/prepare-integration-v22.py
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python scripts/resume-integration-v22.py
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python scripts/rebounds-integration-v22.py
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python scripts/finalize-bridge-v22.py
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python scripts/verify-integration-v22.py
python -m unittest modeling.test_integration_v22
```

Completed job IDs return saved receipts; they do not repeat workloads. A new hypothesis, changed source or repaired gate requires a new preregistered revision, not overwriting this run. Preparation refuses changed upstream bytes rather than silently claiming exact replay. No research daemon is promised after this session; the final execution receipt records actual process status.

Stop condition: the preregistered independent component batch completed; further joint optimization is blocked by historical evidence/consistency requirements. Promising conditional mean improvements justify more evidence collection, **not production promotion**.

Machine-readable results: [integration-v22-results.json](integration-v22-results.json).
