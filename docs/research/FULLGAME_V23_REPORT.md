# V23 full-game recovery — research checkpoint

Branch: `research/fullgame-v23`, continued from `research/integration-v22`.
Machine-readable results: [fullgame-v23-results.json](fullgame-v23-results.json).

## Decision

The new research-only event engines complete games while enforcing the tested
joint accounting, clock-budget and participation invariants. The final bounded
batch completed 176 games across 11 actual matchups and replayed the first seed
for each matchup exactly. This is mechanical recovery, **not demonstrated
forecasting accuracy or a production promotion**.

**Zero strictly qualified pregame matchups.** No 10,000-game forecasting batch,
score/player accuracy comparison, Brier score, log loss, calibration estimate or
production-reference comparison was manufactured from final-conditioned data.
The original V20 pause and stricter V21/V22 qualification requirements remain.

## Verified counts

| League | Historical accounting replays | Primary gamebooks | Complete Mode A games in final batch | Exact seeded reruns | Strict pregame matchups |
|---|---:|---:|---:|---:|---:|
| NFL | 3 | 1, plus independent weekly statistics for all 3 | 48 | 3 | 0 |
| CFB | 4 | 4 | 64 | 4 | 0 |
| NBA | 4 | 4 | 64 | 4 | 0 |

Across the 11 replays, **1,503 nonzero/explicit player counting-stat comparisons
had zero differences**; team accounting and final scores also reconciled in the
stated fields. These fields are enumerated by the replay code and JSON, not a
claim that every possible football or basketball statistic was checked.

Historical cases deliberately cover a close game, blowouts, seven made field
goals, NCAA eight-overtime play, NBA overtime, substitutions and unusual source
accounting. No protected test event was selected.

| League | Event | Verified final score |
|---|---|---|
| NFL | Baltimore–Cincinnati, 2024 week 5 | 41–38, OT |
| NFL | Jacksonville–Buffalo, 2024 week 3 | 10–47 |
| NFL | New York Giants–Washington, 2024 week 2 | 18–21 |
| CFB | James Madison–North Carolina, September 21, 2024 | 70–50 |
| CFB | Ball State–James Madison, September 28, 2024 | 7–63 |
| CFB | Minnesota–Michigan, September 28, 2024 | 24–27 |
| CFB | Georgia Tech–Georgia, November 29, 2024 | 42–44, 8 OT |
| NBA | Memphis–Los Angeles Lakers, November 13, 2024 | 123–128 |
| NBA | Miami–Detroit, November 12, 2024 | 121–123, OT |
| NBA | Houston–Minnesota, November 26, 2024 | 117–111, OT |
| NBA | Los Angeles Lakers–Memphis, November 6, 2024 | 114–131 |

Scores are outcome labels used in Mode A, never inputs presented as pregame
forecasts. The JSON is authoritative for exact event IDs and per-field scope.

## Actual repairs

### Separate modes and accounting

`modeling/fullgame_v23/` adds explicit mechanical, conditional and strict-pregame
contexts. Final boxes/participation cannot enter the pregame path. Ordinary
passing outcomes update the quarterback and receiver from the same event;
receptions, completions and their yards reconcile exactly. NFL sack losses
reduce net team passing; NCAA sacks belong to rushing. NCAA TEAM spikes,
kneels and unresolved anonymous attempts stay TEAM credits. Verified lateral
splits preserve a single catch and reconcile passing/receiving yardage.

Invalid actors, off-court credits, contradictory completions/interceptions,
positive sacks, impossible lineups and unavailable-player credits fail checks.
Explicit sourced injury scenarios exclude players and trigger supported
substitutions. Missing replacement-QB evidence or fewer-than-five supported NBA
players raises an error instead of inventing replacements. This is a tested
scenario interface, not a claim of complete historical injury recovery.

### CFB primary-source reconciliation

Independent book statements fixed wrong yardage signs, a sack credited as four
rather than twelve lost yards, credited plays incorrectly marked nullified, and
current rulings obscured by quoted overturned plays. One duplicate secondary
play and two omitted primary events (a field goal and a TEAM spike) were found
in Minnesota–Michigan. Matching requires independently printed team, quarter,
down, field position and action evidence; final totals do not choose a patch.
Ambiguous matches remain explicitly unmatched. Original feeds and forecasts
were not edited.

Inserted primary events use their actual clock anchors; they do not acquire
fabricated provider sequence IDs. Duplicate event detection requires one
primary action, not merely two identical coarsened clock labels.

### Complete-game transitions and clocks

The football core tracks down/distance, field position, possession, score,
quarter, clock, coupled participants and overtime. Repairs distinguish made
from missed field-goal transitions, preserve overtime turnover/punt field
position, suppress irrelevant game-ending tries, condition kneels on halves
rather than every quarter, and include distance in contextual play selection.
Memoization now includes exact influential state and availability; bucket-only
keys could otherwise make draws depend on which earlier game warmed a cache.
The input hash includes the frozen clock artifact.

The frozen V21 interval-censored clock is used without refitting it to scores.
Live/stopped/running phases use 89 NFL stopped-clock anchor observations and 15
explicitly printed CFB snap/end pairs. Unsupported live-play types borrow a
labeled same-league timing prior. These draws do **not** identify each unknown
historical duration. Administrative running-clock consumption, two-minute
rules, season-specific first-down stops and explicit runoff elections have
software tests; a zero source delta is not proof of zero physical duration.

All generated football regulations account for 3,600 game-clock seconds. Source
boundary audits now require actual start/end anchors, not simply four quarter
labels. NFL source anchors cover 3,600 seconds for each selected game. CFB
boundary spans are 3,600 (JMU–UNC), 3,592 (Ball State–JMU), 3,543
(Minnesota–Michigan) and 3,575 (GT–Georgia). The missing 8/57/25 seconds are not
assigned invented physical durations.

### Overtime and basketball

The controller replays all 16 valid primary-book turns of Georgia–Georgia Tech,
including its untimed tries. An administrative restart after a nullified try
is not a new possession. NFL Baltimore–Cincinnati replays its three overtime
possessions (no score, no score, field goal); an end-game administrative feed
row is not counted as a fourth possession. Tests distinguish 2024/2025 NFL
regular-season and postseason possession rights and NCAA rule eras.

The separate NBA engine enforces five-player second budgets, source-supported
rotations, shot/shot-clock events, reboundable misses, linked assists, foul-out
replacements and shared-stat combined outcomes. One-shot trips are not silently
converted into ordinary possession-ending shooting fouls. Actual 2/3-shot trips,
technicals and and-ones have distinct accounting. Corrected same-clock actions
precede the player they replace, rather than treating corrected IDs as time.

All four NBA historical event streams identify their five-player courts.
Player counts match the independent final books. Reconstructed seconds agree
with the books' whole-second rounding; regulation is 240 player-minutes per
team, and each observed overtime adds 25. Two actual NBA OT replays validate
53-minute/265-player-minute games. A deterministic **synthetic software fixture**
also exercises the complete generated NBA overtime path and its 300-second
extension. It is not a real-game accuracy example.

A separately registered search for generated OT stopped after its budget of
96 additional one-game draws, with none found. It was not extended to obtain a
preferred result. It adds no independent forecasting cases and does not
establish an OT probability.

## Evidence recovery and remaining gates

The old NBA injury parser silently skipped continuation pages without repeated
column headings. The new parser preserves verified column geometry and report
edition across pages and retains wrapped reasons. Eight primary dated reports
for the four NBA dates yielded **48 latest event-specific availability records,
25 with earlier-history player identity resolution**. NFL primary reports yielded
**13 designations, 11 resolved**. Unknown/unresolved names remain unknown.
A source modified after the prediction cutoff is rejected. No absent injury
row is interpreted as a healthy player.

Three additional CFB primary pregame documents were fetched. URL dates, PDF
creation metadata and date-only pages cannot establish a publication-complete
injury/starting-lineup snapshot. None supplied all required evidence. Independent
books also exposed erroneous archival CFB event times; final actual-kickoff
observations are retained separately and do not retroactively establish a
pregame cutoff. Original archived timestamps remain unchanged.

All leagues still lack complete, versioned pregame lineup/availability and
participation evidence, correction-publication history, quantified validated
model uncertainty and a model-bound certificate on at least 12 independent
full games. Football also needs timestamp-verified historical weather forecasts.
NFL and CFB pace/possession realism is not certified: some conditional generated
play-count distributions miss their observed counts. More physically identified
clock/administrative evidence and held-out pace validation are required.

The generator currently conditions kicks on legal touchbacks and supports
ordinary plays. Rare live-ball penalty enforcement, returns, timeout strategy,
postseason unfinished drives across an overtime boundary, and NBA retained-
possession/flagrant sequences are not fully generatively validated. Some are
replayed or unit tested, which does not certify their full joint law. Historical
NBA possession tallies are partial, not falsely advertised as exact. Full
11-player football personnel histories have not been recovered. **No full-game
production gate is released on these partial checks.**

V22's corrected CFB counting inputs are consumed by the new source-ID-preserving
mechanical adapter. The isolated NFL passing point-head result does not supply a
validated joint opportunity distribution; it was not converted into invented
full-game probabilities. Rejected V22 NBA rebound challengers remain rejected.

## Verification, resources and preservation

- Full existing Python suite: **407 tests**, no failures, one initial cache-only
  lookup skip. After extending that lookup to the preserved caches, the final
  focused V23 suite ran **50 tests, all passing, no skips**. This includes new
  down/distance cache, boundary-anchor and complete generated-OT checks.
- Final registered mechanical run: `verified-r5`, 176 complete games plus 11
  identical first-seed reruns; **10.376 CPU seconds**, 10.261 wall seconds.
- Controlled V23 receipts at report time: **306.165 CPU seconds**, including
  failed diagnosis and 151.395 CPU seconds for the full existing test suite;
  peak process RSS **1,045,836 KiB**. This excludes separately unmetered ad hoc
  engineering CPU. Supervised time and conservative engineering reservations
  remain in the inherited cumulative 10-hour ledger.
- Preliminary/debug runs and superseded verification revisions are retained
  separately. Repeated trials on the same matchup are never counted as new
  independent games. Source-code snapshots preserve superseded registered laws.
- Hash verification preserved **6,068 inherited artifact files**. All **161
  protected IDs**, including 79 sealed final-test games and locked confirmations,
  remained protected. No production, financial, database, hosting or billing
  operation was performed. No model was promoted.
- No production deployment/browser tests were run: this is an isolated research
  branch with no frontend changes. No work ran on Vercel or the Render frontend.

## Reproduction and resume

Requires the preserved V20/V21/V22 private research data and V23 checkpoint;
full copyrighted gamebooks and unnecessary large datasets are not published to
Git. Source URLs, hashes, protocols, seeds, code snapshots and receipts are in
the checkpoint. The public JSON includes the aggregate comparisons.

```bash
# On this preserved workspace; a completed job returns its receipt.
OPENBLAS_NUM_THREADS=1 python scripts/verify-fullgame-v23.py
OPENBLAS_NUM_THREADS=1 python scripts/recover-fullgame-v23.py
OPENBLAS_NUM_THREADS=1 python scripts/overtime-fullgame-v23.py
OPENBLAS_NUM_THREADS=1 python -m unittest modeling.test_fullgame_v23
```

Do not register over an existing protocol. New sources or code require a new
immutable revision, checksums and budget claim. Preserve the pause and protected
cohorts. Resume strict forecasting only after the missing evidence and joint
consistency certificate actually pass; then use the existing guarded 10,000-game
entry points. This session stops at the documented evidence/realism boundary,
not because prediction superiority was established. No overnight process is
claimed to remain active.
