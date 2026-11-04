# Controlled football and basketball model learning

The offline learner fits and compares independent NFL, CFB and NBA candidates using real historical play-by-play and box scores. It does not run large batches on Vercel or Render, place wagers, modify financial records, or silently promote a research candidate.

The measured results are in [the experiment report](reports/v16-iterative-learning.json), [paired final comparisons](reports/v16-paired-analysis.json), and [the frozen protocol](reports/v16-protocol.json). The app exposes these through Model validation (`/#engine`). Earlier v15 forecasts, diagnostics and final-test periods remain preserved and are not represented as fresh test evidence.

## Scientific protocol

The seeded selection uses three disjoint chronological validation cohorts per league. NFL/CFB training uses completed earlier games from the 2024–2025 source seasons; validation cohorts fall in September, October and November 2025. Their final period is January–early February 2026. NBA uses separate basketball data and mechanics: validation is January, February and March 2026; the final period is April 2026. Parameters and roster features are frozen before each cohort, including throughout the final period. Individual observations from an in-progress game cannot enter training.

Each evaluated forecast runs 10,000 complete games in bounded 2,000-game batches. The simulation generates shared events, rather than independently drawing unrelated player-stat outcomes. Forecasts are written atomically before final-stat retrieval and evaluation. Model and protocol identifiers include exact configuration and source hashes. The sources are retrospective: their original publication/correction times and complete pregame injuries, lineups and weather are not archived. Consequently these are **retrospective research results, with zero strictly pregame-qualified games**, not proven prospective accuracy.

The experiment predeclares three challenger configurations and retains a frozen v15 research reference. There is no validated full-game production champion. CFB scoring repair preserves both the touchdown play and PAT/2-point observation when the provider combines them in one row. Further candidates test empirically conditioned clock durations, stronger regularization, NBA history windows and empirical-Bayes defensive shrinkage. The old code and original Ohio State–USC artifacts remain unchanged.

Selection uses paired calendar-week bootstrapping of score CRPS, multiplicity correction, at least 24 paired games, six weeks and three cohorts. It requires improvement in multiple cohorts and vetoes regressions in score MAE, win Brier/log loss, player CDF Brier, calibration gap, interval coverage, identity coverage and sufficiently populated player categories. A research selection is still ineligible for production without the missing source/lineup evidence. A single good score prediction, or a better average with worse probability reliability, is insufficient.

After validation, selected candidates and a diagnostic finalist are locked. The final period is evaluated once for those locked models and the reference; it cannot change selection. There is no optimization against final-test results. The diagnostic finalist is explicitly unpromoted and can fail reliability gates. A new experimental generation must reserve a new final period; repeatedly sampling the exposed final period would not create new out-of-sample evidence.

## Measurement and limitations

Reports include score MAE/RMSE/bias, totals and margins, distributional CRPS, 50/80/90/95% interval coverage, win Brier/log loss and reliability bins. Player categories and available position labels are retained; absent positions remain unknown. Game type stratification describes the verified final margin and is evaluation metadata, never an input to its prediction. Only exact stable-ID matched actual statistics are graded; an unverified absence is not silently assigned zero.

Player over/under and correlated-event diagnostics use **fixed, predeclared research thresholds**. These are not historical sportsbook quotes, executable contracts or payout/settlement rules, and do not establish betting win rates or profitability. PropLine's inspected official documentation says its archive begins in April 2026, after the football final period. NBA historical quote identity/coverage is not verified for these games. No historical lines were fabricated or blended into independent simulations.

Raw hit probabilities use K/N with Wilson 95% Monte Carlo intervals and binomial standard errors. No absent calibration artifact is invented. More trials reduce sampling error, not uncertainty in team strength, personnel, injuries or model structure. Distribution coverage and calibration are measured rather than asserted. The models still omit or approximate documented special-teams, penalty, personnel, injury, weather and basketball administration effects; this is not a claim of a finished forecasting model or market superiority.

## Local operation and recovery

Use the pinned Python dependencies in `modeling/requirements.txt` and `modeling/requirements-research.txt` on a Linux workstation. The runner uses file locks, two processes and one numerical-library thread per process. It never opens Supabase, MongoDB or R2.

```bash
python scripts/download-learning-v16-data.py
python scripts/train-evaluate-engines.py --prepare --cpu-budget 7200 --wall-budget 7200
python scripts/learning-worker.py
python scripts/recover-learning-draw-order.py
python scripts/check-learning-convergence.py
python scripts/verify-iterative-learning.py
python scripts/report-iterative-learning.py
```

`--prepare` refuses to overwrite an existing frozen protocol. The completed experiment is delivered already; do not call its existing final period a new test. To reproduce an interrupted run, restore its pinned source commit and exact protocol/data versions. The runner refuses changed code rather than silently applying it to old snapshots. The local scheduler entry point detects completed experiments and verifies them without training again. It refuses large research jobs on request-serving Vercel/Render hosts. No hosted cron, paid worker, cloud database or billing plan was added.

CPU usage is accounted in a shared atomic budget across workers and restarts. A running bounded game finishes before the next budget check. The stopping rules cover CPU time, wall time, a validation plateau and the predeclared candidate-iteration budget. The report records the condition actually reached. There are no uncontrolled polling loops, and a second orchestrator cannot start duplicate work.

All run/model/decision files are append-only under `artifacts/learning-v16`; partial writes cannot replace a saved forecast. Recovery checkpoints include the local branch `checkpoint/pre-iterative-learning-20261104`, the same-named GitHub branch, and the frozen scientific source commit `4cf70a08271847f15ee34a25d0babfa190ad423c` on `research/iterative-v16`. The protocol records eight source-file hashes and exact data/dependency versions. Fresh-process verification checks fitted-model hashes, forecast checksums, time cutoffs, game counts, histogram mass and the final selection lock.

Saved runs contain histograms, outcome counts, uncertainty, configurations, seeds and model references. They do not contain millions of simulated plays. Compressed fitted artifacts are shared across games; input datasets are not duplicated into application databases. Compact research exports are separate from source exports. Download these archives for independent retention; optional R2/MongoDB application credentials are not configured, and no claim of an off-site backup of every fitted artifact is made. User financial records, saved combinations, AI conversations and existing cloud research remain untouched.

## Cold-replay repair

A real cold-replay test found that sorting JSON object keys changed categorical participant ordering. With identical fitted parameters and seed, an archived NFL run changed its home-win sample rate from 0.7720 to 0.7744. This was sampling-path drift, not an accuracy improvement. Conditional-clock cohort traversal also required preservation.

The repair reconstructs the original receiver/rusher/QB and clock-cohort ordering from the exact pinned earlier training rows. It verifies participation counts, clock pools, stable identities and unchanged fitted-parameter hashes, then writes versioned `draw-order-v2` sidecars. Original models, forecasts and the failed replay diagnostic remain intact. All 27 fitted football artifacts received checked sidecars; sampled NFL, CFB and NBA 10,000-game cold replays were numerically exact afterward. Independent-seed comparisons stayed within the predeclared sampling checks. These checks add 60,000 complete games across six replicas, with zero new historical games; the initial failed diagnostic adds another 10,000. They are not extra accuracy observations.

Use `modeling.reproducibility.restore_draw_order` with the saved sidecar before simulating a legacy football model. For future model generations, persist explicitly ordered category arrays before any seeded simulation. Reusing a seed alone is insufficient if serialization changes random-draw traversal order. Never overwrite a historical forecast to hide this defect.
