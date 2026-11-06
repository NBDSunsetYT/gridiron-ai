# GRIDIRON AI V21 research checkpoint

Production was preserved. No model was promoted. No overall predictive superiority has been established.

This campaign completed five bounded forecast batches across **702 distinct historical games**, plus a separate CFB timing-component evaluation. It repaired identifiable data and reporting defects, tested structural opportunity models, and retained the original forecasts, failed experiments, and V20 checkpoints. The original V20 accuracy-first pause remains unchanged.

## Actual evaluation coverage

| League | New player-projection games | Player/stat observations | Evaluation seasons |
|---|---:|---:|---|
| NFL | 113 | 12,424 | 2024 and 2026 |
| CFB | 235 | 24,298 | 2024, 2025, 2026 |
| NBA | 354 | 98,661 | 2024–25 and 2026–27 |
| Total | **702** | **135,383** | |

These are **conditional historical point-forecast evaluations**, not 702 fully simulated games. Twenty-nine selected older CFB games lacked the existing minimum of three earlier team/opponent appearances and produced no graded forecast. A locked attempt to expand into November 2025 CFB and December 2025 NBA found only nine new CFB games and no eligible NBA games after prior-exposure exclusions. Those results were retained without relabeling previously examined games as untouched tests.

**Zero new complete-game Monte Carlo simulations were run.** Strict pregame evidence and full-game consistency checks remain unresolved. Additional trials would not repair those inputs. No raw hit rates were presented as calibrated probabilities.

## Confirmed defects and repairs

### CFB clocks

ESPN can assign the same displayed clock to consecutive plays. Treating those differences as exact zero physical runoff distorts pace. The new research component models uncertain positive clock charges with an interval-censored distribution, constrained by independently printed drive boundaries. It does not pretend to recover exact snap durations.

- Fitted on 600 earlier drive blocks from 214 games, before September 20, 2024.
- Evaluated on 372 held-out drive blocks across 28 games; observed play sequences are conditioning information, so this is a timing-component test rather than a pregame forecasting test.
- Drive-duration MAE: **37.039 → 25.351 seconds**. Game-mean paired MAE delta: **−12.456 seconds**, bootstrap 95% interval **[−15.745, −9.294]**. The latter uses equal game weighting rather than equal drive weighting.
- Three independent official gamebooks contained 32, 19, and 24 distinct drives. Their intervals had no overlaps or invalid regulation boundaries; reported quarter possession totals sum to 900 seconds.
- Nineteen drives, containing 78 timed plays, passed exact independent down/field/action sequence checks. Fifty-three recorded zero intervals were reconstructed probabilistically. Maximum sum-conservation error was below 6e−14 seconds.
- Unassigned regulation time of 32, 35, and 13 seconds was reported explicitly. It was not silently allocated or assumed to be proven kickoff time.

Administrative runoff, incomplete sequences, field-position discrepancies, and unverified timing-regime state still prevent declaring the complete-game clock gate resolved. Early failed parser/reporting receipts remain in the checkpoint. Fixed model fits were reused for subsequent reporting repairs.

### CFB player opportunities and accounting

The raw 2024 source contains **351 pass attempts with negative anonymous passer IDs**. A game-wide `TEAM` player bucket can combine those IDs across opponents. Known quarterbacks also lose some incompletions when participant identification is missing. Updating aggregate player statistics before rejecting unsupported live-ball penalty observations creates another accounting risk.

The Michigan–Minnesota diagnostic demonstrates the defect: the archived quarterback attempt counts were 15 and 34, while the independently published player boxes report 18 and 41. The collapsed team bucket produced incorrect team opportunities. This was established from counting-stat evidence, without tuning final scores.

The repair reconstructs historical appearances from separate published player/team box tables, using exact game, team and athlete IDs. It keeps unassigned team credits separate, includes NCAA sack/rushing accounting as published, and never guesses which quarterback made an unidentified pass. It preserves the original archive.

**2,461 historical games reconciled across the core passing, rushing and receiving counting statistics; 42 inconsistent games were quarantined.** All six team offensive-play totals in the three independent gamebooks reconciled exactly after repair: 73/79, 71/63, and 66/61. Team completion counts now include the incompletions omitted by the identified-player PBP subset.

Targets, dropbacks, original publication times, and full play-level penalty treatment remain separate unresolved fields. Correct counting statistics did **not** automatically improve held-out projections; see the results below.

### NBA minutes and rebound opportunities

The research adds participation-gated starter/bench workload heads and constrained team-minute budgets. Upcoming starters remain uncertain unless a verified announcement exists. Historical actual starting states are used only for earlier training games.

The on-court reconstruction follows period and descending game clock, using sequence IDs only as tie breakers. This fixes late-corrected substitution IDs appearing after events that actually occurred later. It retains ambiguity when substitutions cannot be reconstructed. There were 179 earlier training games with fully identified credited-rebound exposures and 45 recorded reconstruction failures. These exposures are not claims to identify every missed-shot opportunity or every player's exact minutes.

On-court rebound heads did not establish an improvement over the simpler minutes-proxy head. A further exposure-shrunk efficiency model also failed to consistently beat the existing hurdle control. Those complexities were not accepted as superior models.

A source-repair reporting defect stored 1,114 already-computed NBA state-head predictions at the record top level instead of inside `predictions`. A versioned schema adapter graded those original pre-outcome values. No model was refitted and no archived forecast was overwritten.

### Protected evaluation cohorts

All 79 sealed final-test games remain excluded from evaluation and training. Their outcomes were not used for tuning.

The final audit found that an earlier new-season NFL fit used seven older locked confirmation games in its training history, and an earlier new-season NBA fit used 74. Although those games preceded the new forecast dates, that reuse did not satisfy the requested locked-cohort policy. Those fits remain diagnostics and are excluded from promotion evidence.

The new protection module excludes **both the 79 sealed games and all 82 locked confirmation games** from future training, historical feature construction, and evaluation. A subsequent clean batch used different matchups and verified zero protected training overlap. Original confirmation results and files remain unchanged.

## Clean confirmation results

Fixed model parameters were used after the protection repair. No final test set was repeatedly optimized. Confidence intervals resample whole games; observations are player/stat pairs. These are exploratory conditional comparisons, without a multiple-comparison claim of overall superiority.

| League / statistic | Games / observations | Reference MAE | Candidate MAE | Paired difference, 95% interval |
|---|---:|---:|---:|---|
| NFL passing yards: rolling average → existing hurdle | 33 / 126 | 54.283 | 47.192 | −7.090 [−13.208, −0.844] |
| CFB passing yards: raw-history hurdle → box-repaired hurdle | 40 / 233 | 49.511 | 49.855 | +0.345 [−0.093, +0.803] |
| NBA minutes: existing hurdle → starter-state head | 15 / 411 | 6.075 | 5.960 | −0.115 [−0.230, −0.0004] |

The NFL result supports the existing hurdle model against rolling averages on this sample; it does not establish a new model's superiority over the production champion. The CFB correction improves historical accounting but has not demonstrated better forecast accuracy. The NBA interval is marginal on only 15 games and is insufficient for promotion.

Earlier NBA windows also disagree: on 200 November 2024 games the starter-state head was slightly worse than the hurdle control (5.871 versus 5.838 MAE; delta interval crossed zero). It improved on 100 December 2024 games (6.220 versus 6.375). That instability remains material.

### Higher pregame-volume slices

Known-roster evaluations include players who subsequently record zero opportunities. Those observations can make overall MAE look deceptively small. These additional slices use **earlier rolling opportunity forecasts**, not current outcomes, to identify higher-volume players:

| Slice | Games / observations | Reference MAE | Candidate MAE | Paired interval |
|---|---:|---:|---:|---|
| NFL passing yards, prior attempts ≥10 | 33 / 73 | 75.732 | 62.155 | [−23.787, −2.952] |
| CFB passing yards, prior attempts ≥10 | 40 / 91 | 83.203 | 83.050 | [−1.181, +0.874] |
| NBA minutes, prior minutes ≥20 | 15 / 154 | 6.528 | 6.429 | [−0.320, +0.113] |
| NBA rebounds, prior minutes ≥20 | 15 / 154 | 2.397 | 2.326 | [−0.228, +0.092] |

CFB passing and NBA rebounding therefore remain weak categories. No improvement is established in those higher-volume slices. The aggregate artifact also preserves RMSE, bias, median error, sample counts, and the largest individual errors.

## Error attribution and candidate decisions

Exact symmetric opportunity × efficiency decompositions reconcile to total projection error. They describe arithmetic contributions, not causal effects of injuries or coaching. Opportunity error was larger in approximately 60% of decomposable CFB passing cases and 66% of NFL passing cases in the first batch. Zero-opportunity cases were reported separately rather than assigned invented efficiencies. Separating pace, injury effects and lineup effects causally remains unsupported by the available evidence.

Compared families included rolling averages, opponent-adjusted averages, regularized regression, regularized player/team partial pooling, gradient boosting, opportunity/efficiency hybrids, hurdle models, team-budget shares, starter-state minutes, on-court/proxy rebounds, exposure-shrunk rates, and proportional workload reconciliation.

- **Reject CFB team-budget shares as an accuracy upgrade:** first-batch passing-yard MAE worsened from 50.784 to 53.693 versus rolling averages, with a paired interval excluding improvement.
- **Do not retain exposure-shrunk efficiency as a better champion:** it did not consistently beat the hurdle control on new samples.
- **Retain accounting and clock repairs for research:** their specific consistency/component checks passed; full-game promotion requirements remain unsatisfied.
- **Retain NBA starter-state minutes for further research only:** some independent windows improved, but earlier-window inconsistency, small clean sample size and unresolved evidence prevent promotion.
- **Promote no model.** No candidate has passed the required joint score, player-category, probability, uncertainty, data-quality and cross-window guardrails.

No new moneyline Brier scores, log loss, calibration curves, team-score errors or prediction-interval coverage are asserted in this phase. Qualified joint-game forecasts were not generated. No verified historical prop thresholds were newly ingested, so there are no invented over/under, EV, betting-profit or market-baseline results.

## Sources and evidence limits

- Public nflverse PBP and stable identifier crosswalks; a fresh 2026 season was checksum-pinned.
- SportsDataverse ESPN-derived CFB PBP and separate player/team boxes for 2024–2026; NBA boxes including the new 2026–27 season.
- Official ESPN final summaries, used for grading after forecast files were frozen.
- Official UNC, Ball State and Michigan gamebooks for independent CFB measurement checks.
- Official Bengals injury and Giants projected-depth-chart articles: 85 facts, 72 mapped identities. Projected depth is not confirmed starting participation.
- Additional official NFL 2026 week-six/seven articles: 173 explicit designations across selected games, 49 mapped through exact earlier-team GSIS identity history. An after-cutoff report was rejected. Missing positions and uncertain designations remain explicit.
- Official historical NBA injury PDFs: 339 facts, 217 mapped identities, covering 41 of the 200 first-batch NBA games. They do not provide complete verified starting lineups.
- One timestamped secondary CFB report recovered Drew Allar's reported availability before Ohio State–Penn State. It is not a recovered primary conference list or proof of unrestricted usage.

The canonical-article parser separates article dates from related-content dates and accepts a WordPress article only when its host/path identity and `mainEntityOfPage` agree. Full names are joined through exact IDs observed on the relevant team earlier; ambiguous identities remain unresolved. Recovered facts were not retroactively inserted into already-graded forecasts.

There are **no strictly qualified pregame forecasts** in this checkpoint. Original publication/correction times of historical statistics, complete injuries, confirmed lineups/participation, weather forecast history where required, and validated model uncertainty remain incomplete. The 22,027 game/player evidence records explicitly preserve missing domains. Unknown is never classified as healthy.

Existing PropLine and DraftKings Predictions integrations were left unchanged. Sportsbook lines were not substituted for event-contract prices. No API credentials, subscription changes, production database writes or financial-record changes were made.

## Execution, tests and resource controls

The runner inherited V20's compute ledger and checkpoints instead of resetting its allowance. Receipts include successful, failed and reporting-repair jobs. At the numerical checkpoint, measured V21 jobs consumed approximately **860 CPU seconds and 968 wall seconds**; the largest job peaked at **1,791,428 KiB RSS**. These figures exclude unmetered engineering-command CPU. The ledger separately records observed controller time and conservative setup/unobserved wall charges. Exact current values are in `overnight-v21-results.json`.

The 10-hour cumulative allowance was not exhausted. The stop condition was completion of the registered component batches with unresolved strict evidence/full-game gates and no overall validated challenger. The campaign did not reach a fabricated “20 failed candidates” or “10 hours running” milestone.

Controls include one research-job lease, duplicate-job suppression, preserved receipts, 4 GiB address-space limits, 3 GiB parent RSS checks, disk-space guards, wall/CPU timeouts, bounded child groups, accounted child CPU, single-thread BLAS pools, and conservative provider retries. No hosted Monte Carlo jobs were invoked and no paid resources were created.

Actually executed:

- **350 Python regression tests passed** after the box/schema repairs; the final protected-cohort guard was additionally covered by the **37-test focused V21 suite**, which passed.
- **793 JavaScript tests passed across 115 files**, including existing ledger, API-failure and model-quality guards. JavaScript/UI source was unchanged afterward.
- Three real gamebook accounting fixtures and the held-out clock component passed their documented checks.
- The bounded resume command was exercised and skipped completed jobs; it did not launch duplicate simulations.
- Protected V20 file checksums were verified throughout. Production `main` is checked separately during publication.

These tests do not constitute a new production deployment, device installation test, production database persistence test, or proof that a model beats market prices.

## Reproduce and resume

Branch: `research/overnight-v21`, based on the preserved V20 checkpoint. Code changes live in `modeling/evidence_v21/`, `modeling/test_evidence_v21.py` and the `scripts/*v21.py` research entry points. Aggregate results and preregistered selections are in `docs/reports/overnight-v21-*.json`.

In the existing research workspace:

```bash
cd /workspace/gridiron-ai
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python scripts/resume-v21.py
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python scripts/resume-v21.py --run
python -m unittest modeling.test_evidence_v21 -q
```

Completed jobs are immutable and skipped. After this checkpoint the registered queue is complete; the resume command reports the evidence pause rather than inventing more work. A new candidate or recovered source requires a new preregistration, preserved source hashes, and the unchanged evidence checks. The 79 sealed games and 82 locked confirmation games must not be reused to tune it.

Private checkpoints under `artifacts/overnight-v21/` retain fitted parameters, forecast/grade snapshots, random seeds, source versions, environment versions, failures and runtime accounting. No simulated play archive was created. Public Git contains code, selections and aggregate research results, not upstream datasets or private user records. Recreating a fresh workspace requires the retained V20 checkpoint and checksum-matching source data; a changed upstream release must become a new version, not silently replace an old one.

Execution was real and bounded, including detached processes that were observed while this environment was active. Persistence across a cloud-machine shutdown is not guaranteed. **The campaign is checkpointed and stopped; it is not claimed to continue overnight while inactive.**
