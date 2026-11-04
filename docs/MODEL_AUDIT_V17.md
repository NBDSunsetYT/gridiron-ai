# Continued model audit — 4 November 2026

No model was promoted. This audit reuses archived real-game forecasts and verified outcome records; it generated no new Monte Carlo forecasts and did not tune on an exposed final test.

## Evidence and stopping rule

The analysis covers 342 distinct archived development games: 124 NFL, 174 CFB and 44 NBA. Of these, 24 games per league form the later three chronological cohorts; the older 100 NFL, 150 CFB and 20 NBA games are a separate descriptive audit. Different model/input versions are not silently pooled into a calibrator. All are retrospective; originally published injury and lineup archives remain incomplete.

The calibration sweep completed 36 engine/method configurations, with two expanding chronological evaluation windows per configuration. Regularized Platt scaling, temperature scaling and isotonic PAVA were fitted only to earlier cohorts. Three NBA category/position mean-shrinkage settings were also explored. These corrected means are diagnostic; they are not coherent new basketball game distributions.

The predefined candidate grid finished without a credible qualifying improvement. Promotion remains blocked by fewer than 200 distinct suitable training games per method, fewer than three independent validation windows, unverified historical availability and no fresh untouched final period. The compute budget was not exhausted. Further tuning on the already exposed final period was refused.

## Later development games — original vs candidate

| League | Configuration | Team-score MAE | Home-win Brier | Margin 90% coverage |
|---|---|---:|---:|---:|
| CFB | conditional-clock | 10.566 | 0.1738 | 87.5% |
| CFB | reference-v15 | 17.198 | 0.1669 | 37.5% |
| CFB | repair-conversions | 10.679 | 0.1729 | 83.3% |
| CFB | stronger-shrinkage | 10.208 | 0.1789 | 95.8% |
| NBA | conditional-clock | 8.883 | 0.2258 | 100.0% |
| NBA | reference-v15 | 9.437 | 0.2306 | 100.0% |
| NBA | repair-conversions | 10.096 | 0.2449 | 100.0% |
| NBA | stronger-shrinkage | 9.183 | 0.2354 | 100.0% |
| NFL | conditional-clock | 7.318 | 0.2315 | 91.7% |
| NFL | reference-v15 | 7.298 | 0.2304 | 95.8% |
| NFL | repair-conversions | 7.298 | 0.2304 | 95.8% |
| NFL | stronger-shrinkage | 7.341 | 0.2333 | 91.7% |

These are development comparisons, not new untouched-test successes. `reference-v15` is the frozen research reference, not an established validated production champion. Brier is overall probabilistic loss; its change alone does not isolate calibration from discrimination.

## Why CFB score and probability results diverged

Scoring repairs change both the level and distribution of scores. The reference margin variance averaged 56.05; repaired variants averaged 263.71–321.05. Margin interval coverage improved substantially, while favorite confidence rose from 71.9% to approximately 76.7%. This is not evidence that merely adding variance fixes win probabilities.

The conversion-repair candidate made fewer wrong winner-direction calls (5 versus 6 of 24) but incurred large probability regressions in several games. For cfb:espn:401756944, the home probability rose from 44.95% to 67.50%, although the home team lost; its Brier contribution worsened by 0.2536. The stronger-shrinkage variant moved it to 72.92%. These examples diagnose paired probability shifts, not a rule fitted to those game outcomes.

Mean score error and winner probabilities measure different features of a joint distribution. Touchdown/conversion repair improved score levels without validating matchup-relative strength or probability reliability. Source-matched score covariance summaries, touchdown/player errors, coverage and per-game checksums are in development-audit-v17.json and calibration-v17.json. No new arbitrary variance multiplier was introduced. At 10,000 games the maximum binomial Monte Carlo standard error is 0.5 percentage points; the multi-point probability shifts are changes in model assumptions, not proof that more trials improve the underlying model.

## Rolling calibration — reference model only

| League | Method | Raw Brier | Corrected Brier | Paired 95% bootstrap delta |
|---|---|---:|---:|---|
| CFB | isotonic | 0.2462 | 0.2474 | [-0.0535, 0.0717] |
| CFB | platt | 0.2462 | 0.2499 | [-0.0153, 0.0274] |
| CFB | temperature | 0.2462 | 0.2524 | [-0.0255, 0.0465] |
| NBA | isotonic | 0.2290 | 0.3178 | [0.0182, 0.1682] |
| NBA | platt | 0.2290 | 0.2641 | [-0.0032, 0.0753] |
| NBA | temperature | 0.2290 | 0.2349 | [-0.0182, 0.0319] |
| NFL | isotonic | 0.2745 | 0.3011 | [-0.0715, 0.1129] |
| NFL | platt | 0.2745 | 0.2719 | [-0.0425, 0.0324] |
| NFL | temperature | 0.2745 | 0.3083 | [-0.0150, 0.0799] |

Each pooled calibration result contains 16 held-out development games (8 per window). Games, rather than correlated player rows, are the bootstrap unit. Negative deltas favor the candidate. These intervals are exploratory and are not adjusted for selecting among many candidates. No selection met the full promotion gate. In particular, isotonic NBA recalibration deteriorated on the later windows, illustrating small-sample overfitting.

## NBA limitations and follow-up

Earlier validation improvements did not generalize to the already inspected final period; that final period was not used again for fitting. A separate minute audit matched 447 player-games across the 24 NBA development games using exact IDs in the local final box-score archive. Reference minute MAE was 6.451, RMSE 8.177 and bias −2.393 minutes. The existing challengers barely changed those errors (MAE 6.452–6.453), so their scoring changes did not repair workload prediction. These 447 correlated rows are not 447 independent games. Category-specific regularization errors are reported separately. Minute accounting consistency is a mechanical check, not proof of accurate expected minutes. Missing original starter/injury/rotation reports prevent causal attribution to injuries, substitutions or coaching.

Historical executable player-prop lines were unavailable. Fixed evaluation threshold grids are explicitly diagnostic thresholds, not historical sportsbook markets. No market-price blend or profitable edge is inferred. Player-stat MAE, RMSE, bias and coverage appear by category in the JSON artifacts; no combined-unit player MAE is a promotion criterion.

## Reproduce locally

```sh
OPENBLAS_NUM_THREADS=1 python scripts/calibration-audit-v17.py --cpu-seconds 60
OPENBLAS_NUM_THREADS=1 python scripts/archived-development-audit.py
OPENBLAS_NUM_THREADS=1 python scripts/nba-minutes-audit-v17.py
python -m unittest modeling.test_calibration_research
```

The main sweep consumed 1.124 local CPU seconds and 1.126 wall seconds, with 120.6 MiB peak RSS. The legacy descriptive audit consumed 0.770 CPU seconds. These are local research-process measurements, not total session or billed hosting CPU. Provider requests and new simulation runs were zero.

Original forecasts, model artifacts, prior final-test reports and financial records were preserved.
