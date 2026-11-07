# V28 — forecasting and participation repair

Research branch: `research/forecast-certification-v28`, from V27
`4ed0136844df1537e44973296da6d8dbe9e61c22`. First published checkpoint:
`e8453c9f13dcf824511f2e6d7a3d5be4c7860689`.

**No new strict full-game matchup qualified. No candidate was promoted.**
The work repairs missing data and testable mechanics; it does not establish
full-game predictive accuracy. Main, staging, financial data, registries,
protected cohorts and all original forecasts remain unchanged.

## NBA: confirmed root cause and executed comparisons

The V27 bank was fed history ending in June 2026. A 2026–27 season file was
already owned, but the default loader never included it. Current roster IDs
therefore met obsolete team membership, usage and minutes histories. The new
explicit opt-in loader uses recent data without changing old experiments.
The fresh release admits 122 games, rejects one inconsistent box, hashes both
source editions and quarantines missing minutes or duplicate participant IDs.
An ESPN final-box `active` flag never becomes pregame health evidence.

The roster-aware prior uses earlier history across teams and empirical-Bayes
role priors for sparse players. Conditional scenarios explicitly distinguish
unknown participation from sourced out/available/restricted statuses. Four
chains sample capped minute distributions conditioned on a complete modeled
participant set and the 240-minute team budget. Five-distinct-player lineup
tapes conserve individual minutes; overtime has a separate 25-minute budget.
Foul-driven replanning and lineup-conditioned shot/rebound certification are
not completed by these rotation tests.

| Conditional diagnostic | Games / observations | Reference MAE | Candidate MAE | RMSE reference → candidate | Game-paired MAE difference, 95% CI |
|---|---:|---:|---:|---:|---|
| Gaussian rotation, development | 15 / 389 | 4.9165 | 5.9132 | 6.6280 → 7.4213 | +1.0310 [0.6740, 1.3960] |
| Historical zero-minute hurdle, later confirmation | 6 / 155 | 4.8535 | 4.9661 | 6.7788 → 6.8511 | +0.0814 [-0.3119, 0.5138] |

Minutes are the units; positive differences favor the reference. The hurdle
uses observed historical zero-minute mass, **not an invented probability of
being healthy**. Unknown status still requires a declared, unweighted active
scenario. Historical DNP causes remain confounded with injuries and coaching.
Neither candidate wins. All 29 returned development and 12 confirmation team
scenarios passed the R-hat criterion and exact minute budgets. One development
team was withheld for an incompatible active-list scenario. Confirmation
respects sourced available players before selecting uncertain participants.

Development candidate 90% interval coverage was 78.92%, CRPS 4.2238; later
confirmation coverage was 92.90%, CRPS 3.5640. Different cohorts and a changed
source-adjusted reference prevent treating this as a paired calibration gain.
Missing participants: development 10 / 282 actual minutes, including the
withheld team; confirmation two / 16 minutes. Missing final rows are ungraded,
never assumed zero. Final overtime minutes are not graded as regulation minutes.

On 343 common development player rows, stale June-history rolling MAE was
8.3481 versus 4.8965 with recent history. That supports the staleness diagnosis;
it is not a production-champion comparison or strict forecasting superiority.

**Cohort correction:** five development targets had previously appeared as
earlier input games in V26/V27 prospective references. The initial checkpoint
said exposed games were excluded; this audit corrects that statement. Original
metrics and snapshots remain intact and are labeled development diagnostics.
The exclusion now includes those numeric historical-input IDs. The six later
confirmation games have no overlap with these prior inputs or protected IDs.
Even those six remain conditional: corrected box editions were obtained after
their historical prediction cutoffs. They are not strict pregame forecasts or
a sealed final test. No protected outcomes were graded.

## NFL: earlier-input pace validation

Eight new early-2026 source cases were selected before pace grading. Earlier
2025 history was needed because later 2026 cases were already exposed. Each
team uses its previous three games, strictly before the target date; no target
score or participation is used to fit the empirical pools. R1 found no cases
with sufficient within-season priors; that empty run is preserved.

| Conditional clock variant | Returned matchups | Mean plays | Actual plays | Offensive-play MAE |
|---|---:|---:|---:|---:|
| Phase reference | 4 | 153.31 | 118.25 | 35.06 |
| Phase + V27 conditional clock | 3 | 137.75 | 119.33 | 18.42 |

The table's populations differ. On the **three shared matchups**, the paired
game-bootstrap interval for candidate-minus-reference play MAE is
[-20.50, -12.00]. Four trials per variant are a coarse mechanics diagnostic,
not a pace-distribution or probability certification. There are 28 returned
complete mechanical realizations; failed batches may contain unreturned
partial trials and are not counted as successful games. Returned games
conserve 3,600 regulation seconds and pass the existing accounting invariants.

The candidate still overproduces plays. Other cases fail missing conversion
support, punt intervals or same-stop clock regimes. Penalties, timeout rows,
drive identities and zero clock anchors are reported, not silently repaired.
Actual labels are PBP, not newly reconciled independent official gamebooks.
V27's clock candidate therefore remains disabled. No 10,000-game forecasting
batch was authorized by the evidence gate.

## CFB: narrower supported mechanics, timing gate retained

Twelve previously exposed mechanics cases contain 522 equal-clock adjacent
anchors and one backward source interval. The interval-censored law gives
15,360 positive latent-clock draws with zero zero-duration samples. These are
clock draws, **not simulated games**. Actual source event times in R2 verify
the fixed clock fit precedes all 12 cases; R1's uniform diagnostic date is
preserved without temporal-eligibility claims. Only one case has complete
quarter boundary anchors, and none has complete administrative timing support.

The rules editor's published 2023 NCAA change supports ordinary Q2/Q4 period
extensions and Q1/Q3 carry-over enforcement. The clock now prevents skipping
a pending untimed down and allows repeated supported extensions. Physical
duration stays unknown; an untimed down does not mean zero physical time.
Support is explicitly limited to the checked 2023/24 regime. Loss-of-down
elections, other seasons and unresolved exceptions are withheld. Existing
season-specific overtime tests remain in the regression suite; no new source
certificate for every historical overtime regime is claimed.

Sources: [NCAA rules editor's 2023 changes](https://footballfoundation.org/news/2023/7/20/important-rule-changes-for-the-2023-college-football-season.aspx),
[NCAA 2024 rulebook library entry](https://ncaa.soutronglobal.net/Public/Default/en-US/RecordView/Index/44240).
The official downloadable book and Minnesota notes exceeded the explicit 4MB
capture limit; no partial PDF was admitted as evidence. A conference policy
page was accessible but lacked canonical original-publication metadata.
Administrative clock, live-ball penalty/untimed exceptions, full pace and
possession distributions, and dated participation evidence still block CFB.
Anonymous TEAM passing credits remain unassigned under the inherited reducer.

## Evidence and new prospective capture

Three dated official NBA reports were recovered for November 4–6, 2026 at
5 p.m. Eastern. Four canonical primary NFL articles cover two source games.
Two explicitly corroborate Cooper Rush as Atlanta's reported starting QB;
the stable-ID match is unique in the owned reference. That static reference
is not falsely described as a historical roster. These are partial facts,
not complete team availability or starter certifications.

Sources include [Patriots inactive lists](https://www.patriots.com/news/week-1-inactives-patriots-at-seahawks),
[Seahawks inactive report](https://www.seahawks.com/news/nick-emmanwori-tory-horton-inactive-for-seahawks-opener-vs-patriots),
[Falcons inactive report](https://www.atlantafalcons.com/news/atlanta-falcons-inactives-week-1-pittsburgh-steelers),
and [Steelers injury report](https://www.steelers.com/news/week-1-injury-report-falcons-x3059).
Individual publication/revision times and checksums are in the evidence artifact.

A **new V28 revision**, captured before the November 8 Chicago–Philadelphia
tipoff, retains the original V27 snapshot. Existing V24 heads now cover 30
roster players, versus 13 in V27. Chicago raw minute sum changes 174.93 →
239.40, Philadelphia 143.60 → 265.00. Coverage improves; compatibility does not.
The 265-minute sum is not forced into 240. Missing heads, uncertain active
lists, rotations and joint shot/rebound distributions still block full games.
Separate conditional rotation scenarios conserve minutes but are not validated
final-stat forecasts. Win/spread/total probabilities and prices remain null.

`V28_NBA_PROSPECTIVE_R1.json.gz` preserves values, features, source hashes and
model-head provenance. A separate binding references the exact component code
checkpoint. `V28_GRADE_INPUT_R1.json.gz` uses the **existing** grader without
refitting. A readiness check retrieved zero target finals and correctly marked
the future game pending. Existing V26/V27 scheduled grading was not changed.

## Tests, resources and continuation

Nineteen targeted component/cohort tests and 85 mechanics regression tests
passed. TypeScript: 795 tests across 116 files passed; typecheck passed.
The first full Python suite passed 587 tests before the final two additions.
The final full suite passed **589 Python tests** in 147.42 seconds;
CPU was 148.77 seconds including discovery, peak RSS 294,104 KiB.
These results are recorded in `V28_VERIFICATION.json.gz`.
An instrumentation run enclosed the suite in an application CPU timer and
interfered with a test that expects no outer signal timer; its one failure is
preserved. The final run uses an OS CPU limit, preserving that test's contract.
Software test counts do not demonstrate forecasting accuracy.

Measured research-script CPU is about 79 seconds, including the empty NFL run;
source/network work and earlier uninstrumented full-suite CPU are additional.
Detailed final-test CPU, memory and wall time are reported separately. No paid
resources, deployment work, production compute or database writes occurred.
The inherited 11 file hashes, registry/bank, pause marker and protected cohort
hash are checked before publication. No old campaign was silently resumed.

Private source bodies, raw datasets and full simulated plays are not committed.
Derived final protocols/results are in `V28_RESULTS_R2.json.gz`; the initial
`V28_RESULTS.json.gz` checkpoint is retained. Exact initial NBA code
editions and results are preserved in `V28_ROTATION_R{1,2}_*.json.gz`. The
rotation experiments' original source editions must be restored in an isolated
worktree to reproduce them. Current code intentionally refuses to rewrite
their frozen protocols with the corrected exclusion policy.

After the pending NBA game is final, grade the saved revision without retraining:

```sh
python - <<'PY'
import runpy
from pathlib import Path
runpy.run_path('scripts/v26-grade.py')['main'](
    snapshot_paths={'R1':Path('docs/research/V28_GRADE_INPUT_R1.json.gz')},
    output_root=Path('artifacts/forecast-certification-v28/grades'),
    public_prefix='V28')
PY
```

Stopping condition: available evidence still fails complete participant,
timing and joint-probability qualification, and the bounded NBA candidates did
not establish superiority. No persistent runner remains active after completion.
Next research requires new evidence or a new preregistered cohort/hypothesis;
increasing Monte Carlo counts cannot resolve these blockers.
