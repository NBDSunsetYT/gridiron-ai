# Market V18 — gated forecaster research

**Primary metric: CLV = null; verified opening/closing quote pairs = 0. No blend weight has been fit.**

## Gate 1 — passed

795 TypeScript tests, 507 Python tests and typechecking passed. The original 500-matchup regression audit completed **5,000,000 complete simulated football games** (NFL 200 matchups, CFB 300), all with accounting reconciliation. Original seeds and 10,000 trials per matchup were retained. 58 migrated fitted parameter sets were checked against their originals; coefficients/families were not refit.

This is an exposed regression cohort, not a new untouched accuracy test. Mechanical corrections do change the generated distribution. The observed deltas were recorded without tuning to improve them:

| League | Games | Team-score MAE original → repaired | Brier original → repaired | Log loss original → repaired |
|---|---:|---:|---:|---:|
| CFB | 300 | 14.7676 → 16.1302 | 0.192973 → 0.193733 | 0.577102 → 0.578153 |
| NFL | 200 | 8.3235 → 7.8476 | 0.239220 → 0.242135 | 0.674068 → 0.682262 |

CFB score error increased, and NFL Brier/log loss worsened. No accuracy improvement or promotion is claimed. The [full report](reports/market-v18-stage1.json) includes original-family-specific deltas, paired game-bootstrap intervals, per-statistic matched errors, and all omitted roster/stat observations. Missing predictions were never graded as zero. Original-version mixtures prevent a simple causal attribution to one repair.

Implemented repairs: current-opponent and league-prior pools with fitted empirical shrinkage; one late-clock definition; stopped-clock spikes/incompletions/out-of-bounds events; source-fitted hurry tempo; separate restart pools; fitted regulation 2PC decisions and conversion success; observed return-TD transitions; position priors/depth order where supported; six target/four carry caps. Missing source rates stay null. NFL season-specific observed kickoff positions are used instead of forcing a false own-25 default.

Old V15.0 and V15.1 artifacts still load; V15.1 retains the preserved legacy runtime. New football artifacts use `football-market-candidate-18.0.0`. Fitted weights, raw data and user records are not published. The original numeric source is saved under the private r5 checkpoint and corresponds to the Stage 1 research commit.

A two-matchup / 20,000-game cache-equivalence benchmark reduced preparation/inference CPU from 138.945 to 26.004 seconds with identical score/player distributions, by reusing source/protection data. This is not a measured whole-service saving. A separate scalar-predictor cache replay matched all numerical outputs over 10,000 games (only fresh `createdAt` excluded): 19.043 → 18.004 CPU seconds. That optional adapter was **not enabled in the 500-game audit**. Initial fixture/metadata-comparison mistakes are retained in the private logs; they did not change any numerical result.

## Gate 2 — pending

Ratings and an independent holdout spread comparison are the next gated stage. Official NFL schedule documentation does not verify named book, capture time or closing status for its historical spread columns. Such values cannot be relabeled as verified closing quotes. No timestamp or price is invented.

Stages 3/4 remain locked until the earlier gates pass. Fitted blend weights, verified CLV samples, historical prop-line comparisons and profitability metrics remain null/unavailable.

## Reproduction and limitations

```bash
# Use the Stage 1 commit and preserved private original source/artifact editions.
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python scripts/market-v18-workers.py
python scripts/market-v18-gate1.py
```

Completed games are reused. Numeric source changes require a new immutable revision, not alteration of r5. The scheduler uses at most two local processes, unique pending-game ownership, read-only shared prepared models, file leases and CPU/wall/memory/disk limits. Nothing ran on Vercel or Render.

Unmodeled or incomplete: publication-complete historical injuries/lineups, causal injury effects, OL/coverage interactions, independently fitted weather effects, full structural uncertainty, live-ball penalties/laterals, separate return-clock/return-decision laws and fully certified season-specific overtime. New fitted spike classes need explicit overtime handling; the migrated six-class audit does not introduce that unsupported class. These limitations block production eligibility.

The prior 90-game interruption checkpoint remains in Git history and the private workspace. The audit was resumed and completed, not discarded. Production, staging, protected cohorts and all financial records remain untouched.
