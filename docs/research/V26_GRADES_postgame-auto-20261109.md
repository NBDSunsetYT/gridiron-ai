# V26 prospective reference grades — 2026-11-09

Edition: `postgame-auto-20261109`. All six declared games returned final ESPN source status; no games are pending. This grades forecasts frozen before the games, without regenerating or fitting anything. These are conditional rolling/opponent-average point references, not validated joint simulations.

R1 was frozen at 2026-11-06T23:33:43.394013+00:00 and published as `f1199452ce1d4b63681695049d936ce5b3e494f2` (verified publication supplied: 23:36:27 UTC). R2 was frozen at 23:46:36.121969 UTC and published as `bd4dd02cdafd128e595803a03d48f3c686d85c2e` (23:49:03 UTC). Both precede the first target at 00:00 UTC November 7. Original file bytes match those commits; internal snapshot/game hashes and all pregame cutoffs passed.

The current branch parent is `20d9c49761397a7f06c6c6c2f9a0ce0bf39a40df`; the grader/parsers match the verified `332e41779f32db333aff5d41ebab134a9637ad1f` checkpoint exactly.

## What was measured

**Six distinct games, two per league; 1,359 revision-specific comparisons:** R1 has 668 player/stat observations plus 12 team scores; R2 has 667 plus 12. Rows within games are correlated and repeated revisions are not additional independent games. Errors use the originally saved mean; medians remain preserved in the detailed grading artifact. Stored calendar alternatives were not retrospectively selected.

| Revision | League | Games | Graded player identities | Player/stat rows | Team-score rows | Missing stat actuals | Withheld player references |
|---|---|---:|---:|---:|---:|---:|---:|
| R1 | NFL | 2 | 33 | 173 | 4 | 1 | 1 |
| R1 | CFB | 2 | 32 | 135 | 4 | 2 | 0 |
| R1 | NBA | 2 | 36 | 360 | 4 | 0 | 3 |
| R2 | NFL | 2 | 34 | 175 | 4 | 1 | 1 |
| R2 | CFB | 2 | 31 | 132 | 4 | 2 | 1 |
| R2 | NBA | 2 | 36 | 360 | 4 | 0 | 3 |

Withheld counts are player references withheld in the original snapshots, not additional failed games. Six missing stat actuals (three per revision) remain ungraded; their exact reasons appear below. Positive bias means overprediction. MAE/RMSE/bias remain in each statistic’s original units; no misleading mixed-unit overall MAE is computed.

## Error metrics, separately by revision

| Revision | League | Statistic | Games | Observations | MAE | RMSE | Bias |
|---|---|---|---:|---:|---:|---:|---:|
| R1 | CFB | carries | 2 | 16 | 3.6771 | 4.4549 | +1.8271 |
| R1 | CFB | interceptions | 2 | 4 | 0.6000 | 0.6481 | +0.4000 |
| R1 | CFB | passingAttempts | 2 | 5 | 9.5867 | 10.4313 | -5.2133 |
| R1 | CFB | passingCompletions | 2 | 5 | 5.5467 | 7.1873 | -4.1333 |
| R1 | CFB | passingTouchdowns | 2 | 5 | 1.0800 | 1.4560 | +0.0400 |
| R1 | CFB | passingYards | 2 | 5 | 55.6400 | 63.3158 | -14.6000 |
| R1 | CFB | receivingTouchdowns | 2 | 21 | 0.5571 | 0.6628 | +0.1508 |
| R1 | CFB | receivingYards | 2 | 21 | 29.0278 | 34.3293 | +4.1008 |
| R1 | CFB | receptions | 2 | 21 | 1.8683 | 2.2100 | -0.0302 |
| R1 | CFB | rushingTouchdowns | 2 | 16 | 0.3219 | 0.4467 | +0.2219 |
| R1 | CFB | rushingYards | 2 | 16 | 18.4010 | 25.3916 | +15.6760 |
| R1 | CFB | teamPoints | 2 | 4 | 9.9750 | 11.2926 | +0.6250 |
| R1 | NBA | assists | 2 | 36 | 1.4528 | 1.9371 | +0.0694 |
| R1 | NBA | blocks | 2 | 36 | 0.5750 | 0.8058 | +0.1972 |
| R1 | NBA | fieldGoalAttempts | 2 | 36 | 3.0347 | 3.9330 | +0.3542 |
| R1 | NBA | minutes | 2 | 36 | 5.4889 | 6.8531 | +0.9972 |
| R1 | NBA | points | 2 | 36 | 4.3556 | 5.8039 | +0.5917 |
| R1 | NBA | pointsReboundsAssists | 2 | 36 | 5.9097 | 7.6009 | +1.0736 |
| R1 | NBA | rebounds | 2 | 36 | 1.9181 | 2.3742 | +0.4125 |
| R1 | NBA | steals | 2 | 36 | 0.7111 | 0.9701 | +0.0389 |
| R1 | NBA | teamPoints | 2 | 4 | 10.5250 | 12.3320 | -0.0250 |
| R1 | NBA | threePointersMade | 2 | 36 | 1.1056 | 1.5243 | -0.1889 |
| R1 | NBA | turnovers | 2 | 36 | 1.2097 | 1.6177 | -0.0181 |
| R1 | NFL | carries | 2 | 14 | 3.6357 | 4.5145 | +3.0643 |
| R1 | NFL | interceptions | 2 | 3 | 1.7333 | 2.3608 | -0.9333 |
| R1 | NFL | passingAttempts | 2 | 4 | 9.8833 | 16.0578 | +6.2500 |
| R1 | NFL | passingCompletions | 2 | 4 | 6.3333 | 10.1714 | +5.3333 |
| R1 | NFL | passingTouchdowns | 2 | 4 | 0.9667 | 1.0446 | +0.3333 |
| R1 | NFL | passingYards | 2 | 4 | 59.8667 | 88.9989 | +59.8667 |
| R1 | NFL | receivingTouchdowns | 2 | 28 | 0.2423 | 0.4608 | -0.0006 |
| R1 | NFL | receivingYards | 2 | 28 | 19.7429 | 23.8544 | -1.4738 |
| R1 | NFL | receptions | 2 | 28 | 1.6107 | 1.7928 | +0.3048 |
| R1 | NFL | rushingTouchdowns | 2 | 14 | 0.3476 | 0.6003 | +0.0333 |
| R1 | NFL | rushingYards | 2 | 14 | 20.0667 | 26.2272 | +14.0524 |
| R1 | NFL | targets | 2 | 28 | 2.0012 | 2.3512 | +0.4238 |
| R1 | NFL | teamPoints | 2 | 4 | 7.1750 | 8.0540 | -3.3250 |
| R2 | CFB | carries | 2 | 15 | 3.3000 | 3.9195 | +1.3267 |
| R2 | CFB | interceptions | 2 | 4 | 0.6000 | 0.6481 | +0.4000 |
| R2 | CFB | passingAttempts | 2 | 5 | 9.5867 | 10.4313 | -5.2133 |
| R2 | CFB | passingCompletions | 2 | 5 | 5.5467 | 7.1873 | -4.1333 |
| R2 | CFB | passingTouchdowns | 2 | 5 | 1.0800 | 1.4560 | +0.0400 |
| R2 | CFB | passingYards | 2 | 5 | 55.6400 | 63.3158 | -14.6000 |
| R2 | CFB | receivingTouchdowns | 2 | 21 | 0.5571 | 0.6628 | +0.1508 |
| R2 | CFB | receivingYards | 2 | 21 | 29.0278 | 34.3293 | +4.1008 |
| R2 | CFB | receptions | 2 | 21 | 1.8683 | 2.2100 | -0.0302 |
| R2 | CFB | rushingTouchdowns | 2 | 15 | 0.3433 | 0.4613 | +0.2367 |
| R2 | CFB | rushingYards | 2 | 15 | 17.7389 | 25.1832 | +14.8322 |
| R2 | CFB | teamPoints | 2 | 4 | 9.9750 | 11.2926 | +0.6250 |
| R2 | NBA | assists | 2 | 36 | 1.4528 | 1.9371 | +0.0694 |
| R2 | NBA | blocks | 2 | 36 | 0.5750 | 0.8058 | +0.1972 |
| R2 | NBA | fieldGoalAttempts | 2 | 36 | 3.0347 | 3.9330 | +0.3542 |
| R2 | NBA | minutes | 2 | 36 | 5.4889 | 6.8531 | +0.9972 |
| R2 | NBA | points | 2 | 36 | 4.3556 | 5.8039 | +0.5917 |
| R2 | NBA | pointsReboundsAssists | 2 | 36 | 5.9097 | 7.6009 | +1.0736 |
| R2 | NBA | rebounds | 2 | 36 | 1.9181 | 2.3742 | +0.4125 |
| R2 | NBA | steals | 2 | 36 | 0.7111 | 0.9701 | +0.0389 |
| R2 | NBA | teamPoints | 2 | 4 | 10.5250 | 12.3320 | -0.0250 |
| R2 | NBA | threePointersMade | 2 | 36 | 1.1056 | 1.5243 | -0.1889 |
| R2 | NBA | turnovers | 2 | 36 | 1.2097 | 1.6177 | -0.0181 |
| R2 | NFL | carries | 2 | 13 | 3.8128 | 4.6703 | +3.4026 |
| R2 | NFL | interceptions | 2 | 4 | 1.4500 | 1.7972 | -0.8500 |
| R2 | NFL | passingAttempts | 2 | 5 | 9.5733 | 14.9561 | +3.3333 |
| R2 | NFL | passingCompletions | 2 | 5 | 5.3200 | 9.0973 | +3.4000 |
| R2 | NFL | passingTouchdowns | 2 | 5 | 0.9200 | 1.0080 | +0.5200 |
| R2 | NFL | passingYards | 2 | 5 | 67.6400 | 89.9832 | +25.0800 |
| R2 | NFL | receivingTouchdowns | 2 | 28 | 0.2423 | 0.4608 | -0.0006 |
| R2 | NFL | receivingYards | 2 | 28 | 19.7429 | 23.8544 | -1.4738 |
| R2 | NFL | receptions | 2 | 28 | 1.6107 | 1.7928 | +0.3048 |
| R2 | NFL | rushingTouchdowns | 2 | 13 | 0.3744 | 0.6229 | +0.0359 |
| R2 | NFL | rushingYards | 2 | 13 | 20.9436 | 27.1109 | +15.8000 |
| R2 | NFL | targets | 2 | 28 | 2.0012 | 2.3512 | +0.4238 |
| R2 | NFL | teamPoints | 2 | 4 | 7.1750 | 8.0540 | -3.3250 |

## Final source identity and outcomes

| League | Declared event | Final score |
|---|---|---|
| CFB | 401856740 | LSU Tigers 13 – 31 Alabama Crimson Tide |
| CFB | 401856743 | Missouri Tigers 20 – 34 Texas Longhorns |
| NBA | 401909288 | Charlotte Hornets 80 – 119 Boston Celtics |
| NBA | 401909294 | Los Angeles Lakers 124 – 118 Portland Trail Blazers |
| NFL | 401873045 | Kansas City Chiefs 35 – 12 New York Jets |
| NFL | 401873050 | Chicago Bears 27 – 24 Tampa Bay Buccaneers |

Only the six declared ESPN summary URLs were requested. Event IDs, final status, team IDs and player-ID/team ownership were checked against both original revisions. No name-only player joins were made. Response checksums and capture timestamps are published in the receipt file; raw response bodies remain private and are excluded from Git. These are public ESPN final-box editions, a secondary provider—not a newly verified official-league cross-check. Later official corrections require a new result edition.

## Missing and zero actuals

There are 1,164 directly published player/stat rows, 20 explicit DNP zero-credit rows, 151 zero-credit rows supported by the existing complete team-opportunity/stat-credit reconciliation, and 24 team-score rows, across both revisions. The zero-credit proofs do not assert health, unrestricted participation or a confirmed starting lineup. Unsupported zeros are not filled.

| Revision | League | Event | Player ID | Statistic | Reason left ungraded |
|---|---|---|---|---|---|
| R1 | NFL | 401873050 | 4596472 | interceptions | unsupported_zero_inference |
| R1 | CFB | 401856740 | 5224789 | interceptions | unsupported_zero_inference |
| R1 | CFB | 401856743 | 5141973 | interceptions | unsupported_zero_inference |
| R2 | NFL | 401873050 | 4596472 | interceptions | unsupported_zero_inference |
| R2 | CFB | 401856740 | 5224789 | interceptions | unsupported_zero_inference |
| R2 | CFB | 401856743 | 5141973 | interceptions | unsupported_zero_inference |

## Interpretation and decision

**No improvement is established.** The NBA reference outputs and errors are unchanged between revisions. NFL passing-yard MAE is 59.8667 on four R1 observations versus 67.6400 on five R2 observations; these populations differ. CFB rushing-yard MAE decreases from 18.4010 on 16 rows to 17.7389 on 15, but the removed/withheld player changes coverage. Neither difference demonstrates a paired model improvement or regression. Team-score reference MAE is unchanged between revisions: NFL 7.175, CFB 9.975, NBA 10.525. Two games per league cannot establish broad predictive superiority.

Moneyline, spread/total probabilities, Brier score, log loss, calibration, CRPS, interval coverage, market prices and CLV remain **null**. The snapshots contain no supported probability distributions or target market prices. Descriptive historical ranges are not retroactively relabeled prediction intervals. No wagers, market thresholds, prices, payouts or profitability are invented.

Eight targeted grader/zero-credit safety tests passed. A separate arithmetic audit recomputed every MAE, RMSE and bias and verified unchanged source code and forecast hashes. Software tests are not accuracy evidence. No new simulations, training, selection, promotion, paid resources, hosting changes, production/database/financial writes or protected-cohort work occurred. The fresh research workspace did not restore or access private historical/protected outcome archives.

## Files and repeatability

- Detailed immutable comparisons and preserved means/medians: [V26_GRADES_postgame-auto-20261109.json.gz](V26_GRADES_postgame-auto-20261109.json.gz).
- All metrics in CSV: [V26_GRADES_postgame-auto-20261109.csv](V26_GRADES_postgame-auto-20261109.csv).
- Sanitized receipts, source hashes, identity/cutoff checks and missing/withheld counts: [V26_GRADE_RECEIPTS_postgame-auto-20261109.json](V26_GRADE_RECEIPTS_postgame-auto-20261109.json).

Command actually executed (isolated local environment supplied the missing pinned PyArrow dependency):

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python scripts/v26-grade.py --id postgame-auto-20261109
```

For a later correction, use a **different** unique `--id`; retain the original source/grade edition. Reusing this ID intentionally reads its frozen receipts instead of replacing history. No continuously running process was created.
