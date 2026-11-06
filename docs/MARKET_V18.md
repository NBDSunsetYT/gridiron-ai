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

## Gate 2 — blocked, not passed

Implemented `modeling/ratings.py`: opponent-adjusted offensive/defensive EPA, Gaussian ridge partial pooling with blocked chronological alpha selection, separate fitted home/rest terms, and a weekly empirical-Bayes Gaussian process with fitted regression to mean/process variance. The posterior mean drives event offsets; its conditional SD is sampled once per game and shared through regulation/overtime. It does not shrink with the Monte Carlo trial count. MLE ridge offsets affect play/dropback logits, log-link conditional yard means, and exp-link TD hazard. Signed empirical yard residuals remain; TD rows are excluded from conditional-yard fits when a separate hurdle exists. Nonpositive baseline yard means keep the original signed model. This is not a full Bayesian posterior or a validated probability model.

The new `football-market-ratings-18.1.0` artifact has nested `ratings` with its own SHA-256 and a base-model binding. Explicit Stage 1 → rated migration preserves old artifacts and updates the outer SHA. V15.0/V15.1/18.0 still load. No ratings enter an old artifact implicitly. The signed private inference boundary recognizes 18.1; no deployment occurred.

Actual conditional fits, with no final-score or market inputs:

| League/season | Source games | EPA plays | Selected ridge alpha | Six event heads fit |
|---|---:|---:|---:|---|
| NFL 2024 | 48 | 5,891 | 1 | Yes |
| CFB 2024 | 334 | 43,221 | 100 | Yes |
| CFB 2025 | 283 | 36,852 | 10 | Yes |

NFL 2025 has zero eligible rows after the conservative campaign exclusions and is withheld. The 2024 pre-audit dates were chosen from metadata availability, without examining validation outcomes. All new fit rows and blocked-fold training rows strictly precede their respective cutoffs. Protected/exposed audit and confirmation games are excluded. The existing frozen base parameters were not refit. Original source-publication editions and complete pregame availability remain unverified, so these are conditional candidates, not strict forecasts.

**Printed holdout spread correlation: null; qualified quote games: 0.** Official schedule documentation does not establish a named book, capture time or closing status for its historical spread columns. Those values cannot be relabeled as verified closing quotes. No price or timestamp was invented. Gate 2 fails closed and the CLI returns exit status 2; no Stage 3/4 work followed. CLV and all market blend weights remain null. See [the Stage 2 receipt](reports/market-v18-stage2.json).

An initial scope-filter omission was caught and its candidate rejected before grading/promotion. A later empty-input Arrow mask failure was repaired with an automated empty-schema regression. Revisions/logs remain preserved; no failed run was relabeled as success.

The fitted rest term uses days between first verified PBP observations, an explicitly uncertified kickoff/end-of-game rest proxy. Additional solver, source-edition, lineup, injury, full covariance and independent probability-validation work is still required. No new predictive-superiority claim is made.

Stages 3/4 remain locked until the earlier gates pass. Fitted blend weights, verified CLV samples, historical prop-line comparisons and profitability metrics remain null/unavailable.

## Reproduction and limitations

```bash
# Use the Stage 1 commit and preserved private original source/artifact editions.
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python scripts/market-v18-workers.py
python scripts/market-v18-gate1.py
```

Completed games are reused. Numeric source changes require a new immutable revision, not alteration of r5. The scheduler uses at most two local processes, unique pending-game ownership, read-only shared prepared models, file leases and CPU/wall/memory/disk limits. Nothing ran on Vercel or Render.

Unmodeled or incomplete: publication-complete historical injuries/lineups, causal injury effects, OL/coverage interactions, independently fitted weather effects, full structural uncertainty, live-ball penalties/laterals, separate return-clock/return-decision laws and fully certified season-specific overtime. Stage 2 adds explicit spike accounting/masking in overtime; the Stage 1 migrated six-class audit never selected that new class. Season-specific overtime realism still requires certification. These limitations block production eligibility.

The prior 90-game interruption checkpoint remains in Git history and the private workspace. The audit was resumed and completed, not discarded. Production, staging, protected cohorts and all financial records remain untouched.

## Resume after obtaining eligible inputs

Restore the private checkpoints and matching code editions. Use a new immutable revision for new sources; never overwrite a frozen protocol.

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python scripts/ratings-market-v18.py --season 2024 --cutoff 2024-09-30T00:00:00Z --revision ratings-r4
```

The current revision intentionally stops with status 2 at the unavailable market-spread gate. Advancement requires independent, authorized quotes with verified event/side/book, line, capture timestamp, closing designation and provenance. CLV additionally requires genuine opening/closing pairs. Broader historical pregame qualification still requires publication-complete source editions and lineup/availability evidence.

Final Stage 2 software verification: **795 TypeScript tests, 515 Python tests and typechecking passed**. The latest focused ratings/market suite passed 38 tests. No external production test or deployment was performed.
