# Iterative NFL, CFB and NBA research results

The automated local experiment completed **three challenger rounds**, with nine league-level comparisons. None passed every validation gate. Optimization stopped for **validation improvement plateau** in all three sports. No full-game production model was promoted or replaced.

## Actual workload

| Measure | Completed |
|---|---:|
| Distinct real games in this experiment | 112 |
| NFL / CFB / NBA games | 40 / 32 / 40 |
| Validation games / new final-period games | 72 / 40 |
| Graded forecast versions | 352 |
| Complete games per forecast | 10,000 |
| Complete simulated games for accuracy evaluation | 3,520,000 |
| Candidate rounds / league-level decisions | 3 / 9 |
| Fitted model artifacts retained | 41 |
| Strictly pregame-qualified historical archives | 0 |
| Production promotions | 0 |

The earlier v15 study and this experiment cover **640 distinct retrospective games** in total. This experiment adds 100 previously unevaluated games; 12 validation games overlap earlier development/validation evidence. Previous final tests and known Ohio State–USC diagnostics were quarantined. The 40 final-period games here were reserved before evaluation and never used to select or tune a model.

Worker training/evaluation consumed **5,533.85 CPU seconds**, with **3,256.46 seconds elapsed**, under predeclared 7,200-second CPU and wall budgets. Two local worker processes were used, with one numerical-library thread per process. No large historical backtest was sent to Vercel or Render, and no hosted plan or paid resource was changed. These measurements do not establish a percentage reduction in a hosting bill.

## Locked final-period results

Score MAE averages absolute errors for both teams' points. Lower Brier and log loss are better. Results below use identical paired games where a diagnostic finalist exists.

| Sport | Final games | Research reference score MAE | Diagnostic finalist score MAE | Simple scoring baseline MAE | Reference → finalist win Brier |
|---|---:|---:|---:|---:|---:|
| NFL | 16 | 8.700 | No challenger selected | 9.260 | Reference0.1864 |
| CFB | 8 | 19.153 | 11.510 | 8.698 | 0.2866 → 0.3143 |
| NBA | 16 | 10.649 | 11.211 | 13.466 | 0.2462 → 0.2503 |

CFB's stronger-shrinkage finalist reduced score error, but it remained worse than the simple scoring baseline and worsened win-probability scoring. Its passing-yard error also increased. NBA's defensive-shrinkage finalist improved validation score MAE from 9.437 to 8.883, but that did not generalize: its final score MAE was worse than the reference. NFL challengers failed validation, and the original research reference remained the final-period candidate.

The correct conclusion is **no validated overall accuracy upgrade**. Improving one average does not establish a better probabilistic model. The finalists stayed unpromoted even when a descriptive score metric improved.

Final-period paired MAE bootstrap intervals are in `reports/v16-paired-analysis.json`. The final samples span only 3 CFB, 4 NBA and 5 NFL calendar-week blocks; these exploratory intervals are too limited to justify production promotion. The final results were not fed back into selection or parameter fitting.

## Probability calibration and remaining errors

CFB final win log loss worsened from 0.7634 to 0.8354; its reliability-bin calibration gap increased from 0.2955 to 0.3369. NBA final log loss worsened from 0.6848 to 0.6936. Its calibration gap changed only from 0.08435 to 0.08409, which is not evidence of a meaningful general improvement. No raw hit rate was relabeled as calibrated.

Selected stable-ID paired player errors:

| Sport / category | Matched player-game observations | Reference MAE | Finalist MAE |
|---|---:|---:|---:|
| CFB passing yards | 18 | 45.814 | 53.956 |
| CFB rushing yards | 64 | 23.194 | 24.831 |
| CFB receiving yards | 100 | 21.500 | 21.882 |
| CFB receptions | 100 | 1.503 | 1.464 |
| NBA points | 287 | 4.934 | 4.929 |
| NBA rebounds | 287 | 2.236 | 2.229 |
| NBA assists | 287 | 1.449 | 1.452 |

The retained NFL reference's final passing-yard MAE is 70.936 across 32 matched observations; receiving-yard MAE is 19.775 across 237. Those remain important weaknesses. These errors do not prove that injuries, weather or any single cause explains each miss. Unmatched players and uncertain absences are tracked rather than silently assigned zero, and conditional coverage limits the interpretation of player errors.

Category Brier scores, log loss, reliability buckets, position labels where actually available, game-type strata, score/total/margin errors and 50/80/90/95% interval coverage are retained in the JSON reports. Diagnostic over/under grids are predeclared research thresholds, **not verified historical betting lines or executable contracts**. No market-beating or historical betting-return claim is made.

## Confirmed repairs

1. **CFB combined touchdown/conversion rows:** the old loader consumed a combined touchdown/PAT row as a conversion and discarded its offensive play. On whole games completed before 2025-11-15, passing touchdown training labels increased from 84 to 4,952 and rushing labels from 92 to 5,208 after preserving both observations. NFL play counts and labels stayed unchanged; all 24 first-challenger NFL validation forecasts were numerically identical to the reference. This is a verified data-extraction correction, not proof of full-model calibration.
2. **Cold serialization reproducibility:** sorted JSON changed categorical support order and conditional-clock draw traversal. Checked versioned metadata now restores the original order without changing fitted coefficients, saved probabilities or source records. All 27 fitted football artifacts received sidecars. Real NFL/CFB/NBA cold replays at 10,000 games were numerically exact after restoration; independent-seed means and probabilities passed the declared sampling checks.
3. **Controlled experiment execution:** fitting is chronological, snapshots precede final-stat grading, duplicate orchestrators are rejected, completed jobs reopen with zero new simulations, budgets survive restarts, and a new scheduled experiment cannot reuse a previously exposed final period as fresh evidence.

The replay/seed checks ran six additional 10,000-game replicas; a preserved failed pre-repair cold replay ran another 10,000. These 70,000 quality-check games are separate from the3.52 million graded games and add no distinct historical observations. They do not quantify structural model uncertainty or establish improved accuracy.

## Storage, evidence and reproducibility

All 352 compact forecast files occupy **10,737,911 bytes**, averaging **30,505 bytes** each. Complete distributions, outcome counts, seeds, fitted model references, input versions, diagnostics and verified evaluations are retained. No millions of simulated plays were stored. The original Ohio State–USC input/result checksums remain unchanged.

The frozen protocol is committed at `3b6f13ba7b23b11b01b7ea50d692941b462c16e8`, before final-period evaluation. Scientific source is preserved at `4cf70a08271847f15ee34a25d0babfa190ad423c` on `research/iterative-v16`. A recovery branch preserves the prior production source. Fresh-process verification checks fitted-model hashes, restored draw ordering, forecast checksums, temporal cutoffs, histogram counts and the unchanged final selection lock.

Original publication/correction times and complete pregame injuries, starting lineups and weather are unavailable in these public retrospective archives. Therefore **zero games qualify as strict prospective pregame evidence**, despite real final scores and player outcomes being verified. No availability probabilities or injuries were invented to fill the gap.

## Application integration and limits

Model validation (`/#engine`) now exposes the measured experiment, sport filters, candidate rejections, final metrics, player-category errors and reliability diagrams. Public evidence is read-only and cached independently from private-account routes. The AI tool retrieves the archived decisions and measurements without starting training; live language-model generation still depends on the existing server-side AI configuration.

Financial records, existing saved research, Supabase tables/RLS, authentication, PropLine integration, Render gateway and existing forecasting defaults were preserved. No database migration or financial write was made. Optional MongoDB/R2 application credentials remain unavailable; the fitted artifacts are delivered as a downloadable compact archive rather than dumped into the nearly full user database. Download the archive for independent retention.

The local learner is operational and stops at its defined plateau/budget rules. It is not a continuously running production training service. Verified historical lineup/availability coverage, better player opportunity/efficiency modeling and stronger untouched samples are still needed before a production forecasting replacement is justified. Physical iPhone installation was not performed; mobile-browser checks are reported separately in the release verification.

See `ITERATIVE_LEARNING.md` for commands and recovery procedures. The app release status and final browser-test results are recorded separately after deployment.
