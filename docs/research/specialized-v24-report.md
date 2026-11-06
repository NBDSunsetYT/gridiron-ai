# V24 specialized-model implementation audit and research decision

Research branch: `research/dynamic-v24`. Audited starting remote commit: `d4d5fd1c538b188939947942c8772f768f7a0fa5` (tree `8b38ea0dfa185461d6d53cfec6c581f5fd82fd5e`, identical to local checkpoint `ca4902b`).

The requested objective is **not yet complete**. This change implements executable per-statistic model selection and a research connection to shared-event game engines. It establishes limited conditional marginal improvements, but does not establish a superior, strictly qualified full-game forecasting system. No production champion, staging deployment, financial record, hosting configuration or database was changed. No migration merge is authorized by these results.

## Implementation audit

The starting branch was inspected; branch existence was not treated as completion. “Implemented and tested” below describes software and the stated research scope, not production predictive superiority.

| Requested feature | Starting V24 finding | Status at this checkpoint | Evidence and limitation |
|---|---|---|---|
| Per-statistic model selection | Partially implemented: catalog and marginal comparisons existed; some touchdown MAE decisions compared medians with means. | Implemented and tested for conditional marginal research; partial for strict forecasting. | `completion/selection.py` separates expected-value, median and distribution objectives. There are 53 leaderboard categories. No median is accepted as an expected-value head. |
| Automated tournaments | Implemented and tested as conditional research, with incomplete independent confirmation. | Implemented and tested within bounded, immutable protocols. | Inner chronological selection fixes each family before outer grading; confirmation uses that fixed family. Fresh clean NBA confirmation did not reselect families using confirmation outcomes. |
| Different model families | Implemented and tested, with naming limitations. | Implemented and tested with additional opportunity and count adapters. | Rolling/EWMA, opponent ridge, Lasso/Elastic Net, regularized hierarchical effects, gradient boosting, quantiles, empirical Bayes, hurdle, overdispersed count, opportunity-efficiency, residual mixtures and inner-selected mixtures. Not every family is valid for every category. |
| Chronological historical backtesting | Implemented for corrected-history diagnostics; publication-complete pregame evidence missing. | Implemented and tested for conditional diagnostics; strict historical forecasting still blocked. | Earlier-game lags, 48-hour embargo, timestamp-group splits, held-out windows, protected-cohort exclusion and frozen forecast hashes. Current archive editions cannot prove their original pregame publication time. |
| Probability calibration | Diagnostic scoring existed; no approved sport/stat calibrator. | Partially implemented. | CRPS, CDF Brier/log loss/ECE and 50/80/90/95% coverage are evaluated separately from point error. No new probability calibrator was approved. Training-quantile thresholds are not historical prop lines. |
| Joint simulation integration | Missing: selected marginal heads did not feed the full-game kernels. | Partially implemented and mechanically tested. | New bank and conditional adapters feed opportunities, actor weights and efficiency into shared plays/shots. Real NBA automatic cases can still be withheld for unsupported participants; direct TD/game-outcome heads are derived rather than independently forced. No joint forecasting certificate. |
| Momentum and fatigue | Implemented and tested at next-event/component scope. | Partially implemented end to end; original results retained. | Football incremental momentum did not consistently improve; NBA action-type effects improved but shooting success did not. No arbitrary hot-hand or physiological-fatigue multiplier was added. |
| Live game-state updates | Ordering, revisions, freezes, remaining-game simulation and bounded outbox existed and were tested mechanically. | Partially implemented. | No qualified live-provider replay cohort or validated live calibration/latency sample; live forecasts remain disabled by evidence gates. |
| Model versioning | Sparse research registry existed. | Implemented and tested for conditional research. | Content-addressed append-only records, fit cutoffs, source checksums, samples, objective, uncertainty and eligibility. Bank v24.3 also withholds selected candidates until their confirming validation period has ended. |
| Champion-versus-challenger | Marginal comparisons existed, not a qualified joint champion. | Implemented and tested for conditional heads; partial against production. | Per-head fixed-family comparisons, paired game-level intervals and multiplicity controls. Actual production-source NFL algorithm replay was available for a matched subset; most historical production forecast snapshots are unavailable. Existing production champions remain unchanged. |

Original V24 already contained substantive work: 366 conditional point-validation matchups, sequential A/B/C experiments and mechanical/live-prefix tests. Those files and results remain unchanged. This report adds a separate completion batch rather than relabeling the original batch.

## Structural changes and confirmed defects

1. **Opportunity volume and efficiency were insufficiently separated.** New empirical-Bayes/player-rate and regularized team-volume/share components forecast volume before conditional efficiency. Official anonymous team attempts remain unassigned credits. Zero-opportunity-only histories use a population rate instead of causing a missing-player lookup failure. The proposed architecture is executable, but its passing forecasts did not generalize reliably.
2. **MAE could select a touchdown median as if it were an expectation.** Expected-value selection now uses squared error/RMSE; medians use MAE; distributions use proper scores. A low zero-heavy touchdown median does not become a touchdown probability or game-simulation mean.
3. **Averaging marginal draws shrank ensemble tails.** New ensemble samples select a component for each draw, preserving mixture uncertainty. Numerical tests distinguish this from averaging the sampled values.
4. **Marginal heads were disconnected from shared game events.** `HeadBank` validates checksums, exact sport/event/stat identity and timestamps. Football actor allocation and shared completed-pass yard credits now use specialized heads. NBA models feed capped minute budgets, shot allocation and event-constrained rebounds/assists.
5. **NBA two-point allocation used total field-goal attempts.** The specialized research engine uses FGA minus three-point attempts for two-point actor weights. Untagged reference inputs retain identical seeded legacy results.
6. **Team projections could collapse into an anonymous player key.** The bank now separates team estimates from player estimates and rejects ambiguous same-event player/team mappings.
7. **Research candidate availability omitted confirmation timing.** Bank v24.3 becomes selectable only after fit/selection and confirming validation cutoffs. Equal-date versions select the most recent training cutoff deterministically. Earlier v1 mechanics artifacts remain preserved and explicitly mechanical.
8. **Source accounting and participant coverage were inadequate.** Seventeen inconsistent NBA source games were excluded before clean confirmation features. Current last-five-team player universes omit some traded/returning participants; other participants have no usable earlier history. The adapter withholds these cases. It does not silently invent minutes or assume health.
9. **NFL QB scoring labels were missing in the original research packets.** Sourced NFL weekly touchdown/interception labels were restored through a separate protocol with 80 previously unused 2020/2021 matchups. All 64 candidate/window evaluations failed promotion criteria; the missing data was repaired without inventing scoring probabilities. CFB targets remain unsupported by the verified source.
10. **NBA feature preparation exceeded the memory watchdog.** A selection-aware equivalent loop emits only needed rows while preserving every earlier history update. Frozen forecast replay and software tests verify numerical equivalence. The failed 3 GiB attempt is included in resource accounting.

The “hierarchical” family uses regularized player/team effects and empirical shrinkage, not full Bayesian posterior inference. The inherited `negative_binomial` family fits a Poisson log-link mean and estimates overdispersion for a negative-binomial predictive law; it is not negative-binomial maximum-likelihood regression. NBA minutes × game-miss exposure is an explicitly labeled proxy, not observed on-court rebound opportunities. These distinctions affect how much confidence the results support.

## Evaluation design and scope

There are **676 distinct registered matchups** in this batch: NFL 311, CFB 191, NBA 174. Graded game counts vary by statistic because histories and source checks can fail. Do not sum player observations or per-category games to obtain unique matchups.

There were **2,609 candidate/window evaluations**, not 2,609 unique architectures or complete-game simulations. New numerical forecasts are conditional corrected-history diagnostics. There are **zero newly qualified strict pregame full-game forecasts**, **zero joint-game accuracy comparisons**, **zero verified historical market lines graded**, and **zero production promotions**.

Selection uses earlier inner periods. Each fixed family must confirm on both chronological outer windows with at least 30 game clusters per window. Paired bootstraps use 20,000 resamples clustered by game; the protocol uses Bonferroni alpha 0.05/159 for its 53 category × three objective slots. Repeated protocols and conditional-source limitations mean this is not an unrestricted campaign-wide discovery claim. Expected-value wins do not replace probability heads. Distribution decisions also reject material CDF Brier/log-loss or interval-coverage regression.

The primary report uses the latest preregistered confirmation for each category, not whichever outer result is best. NFL passing uses fresh 2020/2021 games; NFL game heads use other games from those periods. CFB confirmation uses September/October 2026 games. NBA March 2026 confirmation fixes the families chosen from the earlier inner selector and removes independently inconsistent source games. The 79 sealed final-test games and locked confirmation cohorts were not opened or reused for tuning. Source editions with known earlier exposure were excluded from new validation; an abandoned zero-eligible NFL 2025 protocol remains recorded.

Full per-statistic results are in [the 53-category leaderboard](specialized-v24-leaderboard.md), [CSV](specialized-v24-leaderboard.csv) and [machine-readable results](specialized-v24-results.json). Records include observation counts, RMSE, probability diagnostics, coverage and paired uncertainty. “Spread” and “total” heads forecast margin and points; they do not grade invented historical market lines.

## Independent conditional results

Each pair below is the earlier / later window. References are rolling historical baselines unless stated otherwise. These are not verified pregame or production comparisons.

| League / statistic | Fixed challenger | Games | Reference MAE | Candidate MAE | Decision |
|---|---|---:|---:|---:|---|
| NFL passing yards | Opportunity pooling | 40 / 40 | 52.697 / 51.603 | 52.374 / 54.182 | Reject: later-window regression; paired superiority not established. |
| CFB passing yards | Refit V20 hurdle reference | 50 / 60 | 55.645 / 51.996 | 51.704 / 52.855 | Reject: first-window point gain did not generalize. |
| CFB passing attempts | Opportunity pooling | 50 / 60 | 7.209 / 5.810 | 9.803 / 6.640 | Reject: worsened opportunity prediction. |
| NBA minutes | Opportunity pooling | 34 / 60 | 5.273 / 4.925 | 5.841 / 6.039 | Reject: both windows worsened. |
| NBA rebounds | Lasso | 34 / 60 | 2.053 / 1.954 | 1.985 / 1.905 | Conditional expected-value support; no strict/joint promotion. |
| NBA points | Inner mixture | 34 / 60 | 4.992 / 4.890 | 4.811 / 4.714 | Keep reference: adjusted uncertainty did not establish superiority. |
| NBA steals | Regularized hierarchical effects | 34 / 60 | 0.802 / 0.764 | 0.744 / 0.734 | Conditional expected-value support; no strict/joint promotion. |
| CFB receiving TD | Residual mixture | 55 / 60 | 0.373 / 0.345 | 0.353 / 0.343 | Conditional squared-error support, separate from TD probabilities. |

The NBA rebound comparison contains 654 / 1,164 graded player observations. RMSE was 2.691 → 2.567 and 2.544 → 2.448. Game-clustered candidate-minus-reference MSE 95% intervals were [-0.985, -0.332] and [-0.690, -0.252]; protocol-adjusted intervals were [-1.268, -0.048] and [-0.916, -0.087]. The units are squared rebounds, not MAE. This supports a modest conditional marginal improvement over rolling averages. It does not establish superiority over the deployed NBA champion or a joint game model.

| League / moneyline diagnostic | Games/window | Raw Brier reference → candidate, earlier | Raw Brier reference → candidate, later | Independently established? |
|---|---:|---:|---:|---|
| NFL | 40 / 40 | 0.2972 → 0.2404 | 0.2600 → 0.2407 | No |
| CFB | 55 / 60 | 0.2672 → 0.1851 | 0.2712 → 0.2074 | No |
| NBA | 34 / 60 | 0.2365 → 0.2254 | 0.2580 → 0.2341 | No |

These classifier scores are not full-game simulation probabilities. No approved calibrator was loaded or silently substituted. The JSON preserves all CFB and other category metrics, including unsuccessful candidates.

For NBA rebounds, diagnostic CDF Brier improved 0.14265 → 0.13718 and 0.13565 → 0.13203; 90% interval coverage was 0.9067 / 0.9270. NFL passing candidate CDF Brier was 0.12135 / 0.11157, versus reference 0.11417 / 0.11164. CFB passing was 0.10110 / 0.12063 versus 0.11835 / 0.11695. Better mean error in one window did not justify hiding later calibration regression. See [reliability plots](charts/specialized-v24-reliability.png); training-quantile CDF thresholds are diagnostic, not traded prop contracts.

### Actual production reference and V23

The NFL production source algorithm (`prop_history` and `hierarchical_props`) was replayed on eligible matched rows; source hashes matched production commit `3ac16f9710e330b2d486097483264293c5a59336`. This is not a recovered historical forecast snapshot or verified historical availability record. In matched subsets of 39 / 40 games and 74 / 76 observations, reference MAE was 65.656 / 65.337; selected opportunity-pooling paired MAE deltas were +0.255 / +3.054, with intervals crossing zero. It did not beat that reference reliably. Do not compare those subset reference errors directly with the different whole-cohort errors above.

Historical production snapshots for other categories were unavailable. V23 empirical kernels are used as mechanical references. Their final-roster/final-rate conditioning prevents honest pregame accuracy comparisons. Reporting those simulations as pregame wins would introduce leakage.

### Error attribution

Symmetric product decomposition separates forecast opportunity and conditional efficiency discrepancies. It is an accounting decomposition, not a causal diagnosis; absolute components can cancel. For opportunity pooling, NFL passing-yard absolute opportunity components were 56.100 / 55.654 yards versus efficiency components 43.947 / 47.664. CFB components were 81.567 / 57.492 versus 45.679 / 42.956. NBA rebound components were 1.069 / 1.083 versus 1.655 / 1.566. This supports prioritizing football participation/volume evidence rather than merely recalibrating win rates. Injury-specific causal attribution cannot be verified from missing historical injury evidence.

## Joint engine integration and gates

The new bank stores 100 checksum-addressed expected-value artifact descriptors. It rejects outcome labels, duplicate rows, incorrect sport/event identities, ambiguous team mappings, tampered pickles/manifests, median-as-mean use, and post-confirmation candidates at earlier cutoffs. Only owned research artifacts can be loaded; there is no public pickle-upload interface.

Football specialized pass/run opportunity odds retain contextual score/clock/down effects. Participants are allocated from supported head shares; completed passes credit identical yards to QB and receiver. A documented equal-unit least-squares projection reconciles passing/receiving yard budgets. This accounting projection is not a fitted ensemble, and projected means need not equal empirical means after game-state constraints. Incompatible attempts/receptions are withheld. Changed availability requires a new supported scenario rather than automatic proportional redistribution.

NBA minutes use a capped team-minute simplex, player rates are per minute, two- and three-point attempts share shot events, rebounds consume eligible misses, assists require made shots, and combined statistics derive from the same ledger. Actual regulation/overtime ledgers remain authoritative. Missing participant heads or impossible shot/point budgets are withheld.

New mechanical suite: **33 cases across 11 matchups; 32 passed, one withheld; 128 complete generated Mode A games** (NFL 36, CFB 44, NBA 48). It injected 702 lagged head values but explicitly retained final-conditioned roster/rate fallbacks. The CFB lagged case `cfb:espn:401628497` was withheld for incompatible supported passing/receiving volume; its reference mechanics were not relabeled forecasts.

Automatic bank-to-engine prototype: five cases passed, generating 20 additional Mode A games (two NFL and three CFB). One NFL case was withheld for incompatible passing/receiving heads. A canonical NBA archive-ID lookup was repaired; all three selected real NBA automatic cases then correctly withheld for unsupported participants. Reused artifacts in revision r2 are not counted as new simulations. Prototype bank v1 artifacts are preserved; version 24.3 timing semantics are separately regression-tested. The small mechanics runs are not 10,000-game forecasting evaluations or predictive-accuracy evidence.

Direct touchdown, moneyline, spread and total marginal heads are not independently sampled into the ledger: those outcomes must emerge from shared scoring. Their joint distributional integration is still incomplete. Even a conditional marginal winner cannot enter a strict forecast without point-in-time qualification, an exact model-bound mechanical certificate, and separate independent joint Brier/log-loss/coverage validation. Strict registry selection also requires validation periods to precede the forecast cutoff. The existing pause and qualification gates were not weakened.

## Remaining blockers and stopping decision

* **All leagues:** zero publication-complete historical matchups in this new batch. Injury reports, expected lineups, participation assumptions and original statistical edition timestamps are incomplete. Unknown is not healthy. Earlier statistical lags do not solve the missing publication evidence.
* **CFB:** administrative clock/runoff, season-specific timing coverage and football pace certification remain incomplete. Existing interval-censored clock and NCAA overtime tests are retained; passing small mechanics cases does not certify realistic possession/play-count distributions.
* **NBA:** available missed-shot totals are not verified on-court exposure. Several selected actual participants have zero or one usable earlier appearance; others were omitted by the recent-team-history universe despite older history after trades or absences. No arbitrary rookie minutes or healthy status was inserted.
* **Production comparisons:** most matching historical champion snapshots are absent. Joint integration has not been tested against an actual production distribution on qualified pregame games.
* **Markets/live:** no verified historical prop thresholds/settlement terms or independently qualified live feed/replay accuracy cohort. PropLine and DraftKings Predictions adapters remain unchanged, and sportsbook odds are not relabeled event-contract prices.

The batch stopped after fresh confirmation and deterministic replay identified these data/qualification limits. More Monte Carlo trials would not recover missing injuries, lineups or timing evidence. No 10,000-game forecast was run for an ineligible matchup. No promotion is justified. Continue only with a new immutable protocol after relevant evidence or a specific mechanical blocker is repaired; do not repeatedly tune the same confirmation cohorts.

## Tests, resource usage and reproducibility

* Focused Python: **123 tests passed**, covering new invariants plus retained V24/V23/V22 tests.
* Frontend: **795 tests in 116 files passed**. TypeScript and Next.js production build passed.
* Frozen numerical replay: **34 fitted forecasts / 24,043 rows**, all selected input hashes identical and point predictions equal to 1e-12; no refits or new simulations.
* Six local production-build Chromium checks passed: NFL/CFB/NBA on iPhone-sized and desktop viewports, HTTP 200, no horizontal overflow, no page exceptions and zero API/model jobs. Physical iPhone/PWA installation and deployed Render testing were not performed in this research task.
* Local standalone research-page startup to HTTP: 593 ms; observed server RSS 189,568 KiB. This is not measured Render performance.
* Controlled research jobs: **1,075.599 measured CPU seconds**, including failed chronology/actor/memory attempts. Successful feature preparation peaked at 1,665,896 KiB; the rejected memory attempt reached 3,150,332 KiB. The final local build separately used 115.062 CPU seconds / 68.609 wall seconds and 1,476,988 KiB peak RSS. An earlier successful build used 120.456 CPU seconds; one intermediate rebuild was interrupted before standalone packaging, with CPU/exit status unavailable, and was rerun successfully. Editing, source acquisition, unit tests and browser work are not all included in controlled-job CPU; cumulative active-time reservations are retained separately.
* All 6,526 inherited checkpoint files and the 41-file initial V24/V23 audit manifest are checksum-verified at final checkpoint. Financial records and production databases were not accessed or mutated to conduct this research.

The research dashboard is `/research/v24/models?sport=NFL` (also CFB/NBA), gated by `GRIDIRON_RESEARCH_V24=1`; default is 404. It reads a compact frozen report, not private records, remote feeds, fitted pickles or simulation workers. [iPhone-sized screenshot](screenshots/specialized-v24-iphone.png) and [desktop screenshot](screenshots/specialized-v24-desktop.png) are local Chromium captures.

Run software verification from the repository root:

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python -m unittest modeling.test_specialized_v24 modeling.test_dynamic_v24 modeling.test_fullgame_v23 modeling.test_integration_v22
npm test
npm run typecheck
GRIDIRON_RESEARCH_V24=1 NEXT_DIST_DIR=.next-v24-modelbank npm run build
node scripts/check-specialized-ui-v24.mjs
```

With the preserved, authorized artifact workspace and recorded dependencies, replay numerical forecasts using:

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python scripts/replay-specialized-v24.py
python scripts/report-specialized-v24.py
python scripts/checkpoint-specialized-v24.py
```

Completed numerical jobs return their existing receipts; they do not rerun experiments. The final leaderboard contains numerical comparisons for 52 categories; CFB targets remain unsupported. A fresh checkout includes source, public protocols, compact metrics, uncertainty, checksums and charts, but not bulk datasets, fitted pickles, private records or proprietary market archives. Exact frozen replay requires the matching owned artifact editions; source URLs alone do not guarantee identical historical editions. New numerical changes must use a new protocol/revision rather than overwriting completed forecasts.

The current research checkpoint is publishable for review. It is **not** a completed accuracy objective, a production model release, or permission to merge research models into Render staging.
