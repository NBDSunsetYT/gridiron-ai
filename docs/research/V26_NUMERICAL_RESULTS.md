# V26 numerical execution and source-backed forecast revision

## Actual work performed

Recovered **59 earlier completed-game sources**, **12 current rosters**, **131 current official NBA report rows**, **142 parseable dated NFL injury facts**, **four primary NFL QB depth charts**, and **33 current SEC availability entries**. No source key, paid resource, production configuration or financial record was changed. Current NFL QB identities were resolved against captured rosters; the older nflverse season was captured before the upcoming cutoff and protected game IDs were excluded before row access.

The official SEC archive's publicly linked report viewer was successfully read as a normal webpage. Its current November 7 entries provide pregame facts captured before those games; its older final statuses do **not** establish when those statuses were originally published. The NBA official live scoreboard returned **HTTP 403**; no bypass was attempted. ESPN's initially captured pregame summaries had no confirmed starting-player box. Availability is still not a complete starting lineup or rotation.

## Confirmed root causes

1. **Availability feed failures:** the NBA parser crashed on a wrapped NOT YET SUBMITTED row. An NFL article had one malformed parenthesis that previously rejected every otherwise valid fact. Both failures were repaired without inventing player identities or health.
2. **Recent evidence rejected by software:** the old 48-hour lag rejected genuinely available NBA data. A narrow source/game/team-bound receipt exception now allows real pre-cutoff editions; corrected historical archives without proof retain the embargo.
3. **QB role errors:** the first simple Tampa Bay reference included Jalon Daniels. The primary current depth chart lists **Baker Mayfield first, Jalon Daniels second**. Revision 2 preserves the original reference, labels Daniels as backup, and adds Mayfield using earlier verified observations. Chicago's Caleb Williams also receives older-season history instead of an arbitrary missing-data projection.
4. **Appearance exposure is not team exposure:** summing independent Boston appearance-only minute averages gives **258.85 minutes**. Its five historical games include overtime, so 240 is not the proper unconditional comparison: historical player minutes average **245.2**, with integer-report rounding. Unequal appearance denominators still inflate the combined reference. This motivates one calendar-exposure candidate, not an arbitrary rescaling of player means.
5. **NFL gross versus net passing:** one Tampa Bay game reports team net passing **−2**, one sack for **2** yards, and individual gross passing **0**. This reconciles as `gross = net + sack yards`. It is not permission to assign −2 gross yards to a quarterback. NCAA passing does not add sacks because NCAA sacks affect rushing. The corrected zero-credit guard checks both opportunities and the requested statistic.
6. **Real game script/weather extremes:** the same Tampa Bay game genuinely finished 16–0 without a completed pass in wet conditions; another was a run-heavy 43–13 win. They are not discarded to improve a metric. Prior role changes and weather/game script limit what five-game averages can support.

## One structural candidate, actual diagnostic results

Compared appearance-conditioned rolling averages with a common calendar-game denominator. Historical missing values are zero only with an explicit DNP or fully reconciled team opportunity/statistic evidence. Anonymous credits remain unassigned. Outcomes were joined after each prediction record was frozen. No algorithm was fitted and no calibration sweep was run.

This uses **24 already exposed games: eight NFL, eight CFB, eight NBA**, with **722 graded player/stat observations** across 18 league/stat categories. Passing has fewer qualifying player observations. These are chronological **conditional diagnostics**, not new independent confirmation: source editions were retrieved after these historical games, and they had already been exposed as inputs for the future cohort.

| League/stat | Games / observations | Reference MAE | Calendar MAE | Game-paired 95% delta interval |
|---|---:|---:|---:|---|
| NFL passing attempts | 6 / 6 | 15.139 | 13.819 | [−3.958, 0.000] |
| NFL passing yards | 6 / 6 | 115.556 | 108.597 | [−20.875, 0.000] |
| NFL rushing yards | 8 / 20 | 32.683 | 32.413 | [−0.694, 0.295] |
| NFL receiving yards | 8 / 48 | 19.995 | 19.314 | [−1.527, 0.156] |
| CFB passing attempts | 8 / 8 | 7.510 | 7.510 | [0.000, 0.000] |
| CFB passing yards | 8 / 8 | 68.083 | 68.083 | [0.000, 0.000] |
| CFB rushing yards | 8 / 26 | 29.253 | 29.452 | [0.000, 0.387] |
| CFB receiving yards | 8 / 37 | 28.007 | 26.845 | [−2.254, −0.160] |
| NBA minutes | 8 / 72 | 4.443 | 4.439 | [−0.0125, 0.000] |
| NBA points | 8 / 72 | 4.319 | 4.317 | [−0.0063, 0.000] |
| NBA rebounds | 8 / 72 | 1.867 | 1.867 | [0.000, 0.000] |
| NBA assists | 8 / 72 | 1.395 | 1.395 | [0.000, 0.000] |

**Decision: no champion replacement or established predictive improvement.** CFB rushing regresses, CFB passing is unchanged, and high-volume NBA results are unchanged. Even favorable exploratory intervals do not qualify a model: samples are small, source editions are conditional, and independent production-reference/joint probability requirements are unmet. Multiplicity-adjusted intervals, RMSE, bias, CRPS, empirical interval coverage, high-volume strata and zero-outcome Brier diagnostics are included in [the full results](V26_CALENDAR_RESULTS_R2.json). The [53-category result view](V26_MODEL_RESULTS.csv) retains existing champions.

The preliminary diagnostic r1 is retained privately with its source editions. Revision r2 strengthens zero-credit evidence and explicitly reconciles NFL net/gross passing; no outcome-driven parameter tuning was performed. Empirical historical bands from three/four observations are not certified 90% prediction intervals. There are no verified historical market lines or settlements in this diagnostic, so moneyline/line Brier, market log loss and CLV remain null.

## Actual prospective outputs

Revision 1 was frozen **23:33:43 UTC** and published as `f1199452ce1d4b63681695049d936ce5b3e494f2` at **23:36:27 UTC**, before the first 00:00 UTC NBA target. Revision 2 was frozen **23:46:36 UTC**, also before all six games. Both are retained with separate hashes.

Selected revision-2 conditional numerical references:

| Player / game | Mean | Median | Evidence and qualification |
|---|---|---|---|
| Payton Pritchard, Boston–Charlotte | 26.8 minutes; 11.0 points; 3.2 rebounds | Full per-stat values in snapshot | Official Available; recent role conditional |
| Walker Kessler, Portland–LA Lakers | 29.8 minutes; 13.4 points; 12.0 rebounds | Full per-stat values in snapshot | Official Available; recent role conditional |
| Patrick Mahomes, Jets–Kansas City | 31.6 attempts; 245.8 passing yards | 30 attempts; 246 yards | Primary projected QB1, not confirmed unrestricted lineup |
| Geno Smith, Jets–Kansas City | 27.4 attempts; 226.0 yards | 30 attempts; 252 yards | Primary projected QB1 |
| Caleb Williams, Tampa Bay–Chicago | 35.6 attempts; 265.8 yards | 34 attempts; 257 yards | Projected QB1; earlier-season backfill exposed in provenance |
| Baker Mayfield, Tampa Bay–Chicago | 22.4 attempts; 149.8 yards | 26 attempts; 145 yards | Projected QB1; wide game-script/weather history, no validated interval |

Four SEC availability facts map to the original prop-reference players: Ryan Coleman-Williams, EJ Crowell and Cam Coleman are Questionable; **Hollywood Smothers is Out and revision 2 withholds his active-role reference**. The other recovered facts include defenders/linemen and players outside the selected reference population. No unsupported opportunity redistribution is performed.

The [revision-2 snapshot](V26_PROSPECTIVE_R2.json.gz) includes all source changes, model/input hashes, means/medians, availability, descriptive historical ranges, calendar alternatives and explicit per-game blocker lists. Revision 1 remains unchanged. These are research references, not validated prop probabilities or production predictions.

## Full-game and accuracy status

Strict full-game forecasts: **0**. Independently evaluated new prospective games: **0 pending final results**. New Monte Carlo games: **0**. Qualified moneyline/spread/total probabilities, final-score distributions and validated prediction intervals are withheld. No fake 10,000-game run or arbitrary probability fills these fields.

Actual remaining blockers: complete verified lineups or supported scenarios; participation/usage restrictions; model-bound historical mechanics/pace certificates; independently validated probability and uncertainty evidence; and exact authorized market prices/settlement rules. CFB administrative clock/pace certification remains incomplete. The 79 sealed final games, locked cohorts, original forecasts and all financial records remain unchanged.

## Postgame measurement and final verification

The saved references now have an executable grader, `scripts/v26-grade.py`. It verifies both snapshot hashes and their actual pre-kickoff capture times, refuses to fetch final statistics until at least four hours after scheduled start, then requires the exact event/team identity and a final source status. It grades each original revision separately and reports withheld/missing rows. It never regenerates predictions, backdates a capture, updates a wager, fills unknown statistics with guesses, trains a model or promotes a winner.

The pregame safety execution retrieved **zero final games** and graded **zero observations**; all six targets were correctly pending. Point errors can be measured after results become available. Probability, CRPS and interval metrics remain null where the saved forecast did not supply that distribution; the grader will not manufacture them after seeing the result. Changed revision coverage cannot be advertised as a paired improvement.

```bash
# After the games finish; a unique grade ID preserves every prior result edition.
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python scripts/v26-grade.py --id postgame-r1
```

The final full checks passed **795 TypeScript tests**, **551 Python tests**, and typechecking. A final explicit-future-availability guard then passed **53 focused tests**. Software receipts identify the scope of each pass; none of these counts is a predictive-accuracy claim. See [software receipts](V26_SOFTWARE_CHECKS.json) and [per-game qualification](V26_QUALIFICATION.json).

All three leagues progressed through real source recovery, numerical capture and the same structural diagnostic. Stopping reason: the current evidence cannot qualify a strict joint-game forecast, the structural diagnostic does not justify promotion, and genuine prospective target outcomes do not yet exist. There is no continuously running simulation campaign.

## Published checkpoint and grading handoff

The code/test checkpoint is `332e41779f32db333aff5d41ebab134a9637ad1f`; its remote Git tree was fetched and exactly matched the local tested tree. Main remains `87961433c9de193c3bed7ccda138d6a95782e506`, and Render staging remains `69714f5a9ac54cea744dd926175a77d4f9cf193a`. Neither was updated by this research.

The [derived diagnostic observations](V26_DIAGNOSTIC_OBSERVATIONS.json.gz) publish all **722** actual values, predicted means/medians, signed errors, game/player/stat identities and training cutoffs. Raw training responses and private source bodies are excluded. These rows retain the exposed conditional-diagnostic label; they do not create an independent test sample.

A one-time postgame grading task was created and verified enabled, targeting **Monday November 9 morning, America/New_York**, after all six declared fixtures. It inherits this research environment and uses the existing grader; no continuously running worker or hosting resource was created. Its stored schedule targets 08:00 with flexible timing. At verification the scheduler's `next_run_time` was still null, so execution is **pending, not guaranteed or claimed complete**. The exact manual command above remains the recovery path. Source outages, postponed games and identity failures must remain pending rather than becoming invented outcomes.

Measured local resource receipts: the full Python checks used **166.618 CPU seconds**, TypeScript **51.468**, typecheck **6.841**, final focused tests **1.393**, and the final structural diagnostic **1.671**. Their unrounded receipts sum to **227.990 measured CPU seconds** for those operations; they are not a fabricated total for the entire session. Earlier source parsing/browser work and preliminary diagnostics were not covered by that total. The diagnostic peak RSS was **298,544 KiB**; the largest observed check peak was **788,196 KiB** during typechecking. New Vercel/Render research workloads: **zero**.
