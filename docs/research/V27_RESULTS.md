# V27 evidence recovery and joint-game certification

Branch: `research/evidence-and-joint-v27`, from published V26 `20d9c49761397a7f06c6c6c2f9a0ce0bf39a40df`. Stage 1 was published and verified as `b9429311cfdb06259b9de2565afb69e8b18d74b7`. No production, Render staging, hosting, database or financial operation was performed. The V24 registry and both original V26 forecast archives passed their inherited SHA-256 checks.

**New strictly qualified full-game matchups: NFL 0, CFB 0, NBA 0. New independent joint probability evaluations: 0. No model was promoted.** The work below advances actual source recovery, mechanics and model execution; it does not establish improved predictive accuracy.

## Verified repairs and source recovery

* The NBA official gamebook parser merged quarter-only and final player tables when PDF extraction inserted a line break. It now recognizes both layouts and rejects duplicate player references. This removed hundreds of false counting/minute discrepancies. Unique same-team full-name suffix aliases handle `Jimmy Butler` versus `Jimmy Butler III`; ambiguous aliases remain unresolved.
* Pregame evidence now rejects an edition modified/available at or after cutoff, including a source with an earlier original publication date. A receipt captured exactly at cutoff is not strictly pregame. This strengthens the existing gate rather than waiving missing evidence.
* Football input hashes now include league, team order, participant ownership and clock-candidate configuration. A changed owner map cannot reuse an old compatibility result.
* The existing model bank compared resolved files against an unresolved artifact root, rejecting legitimate shared-worktree artifacts. Both sides now resolve to the same owned directory. Escaping nested symlinks and content-checksum mismatches still fail.
* Failed/oversized source reads no longer return partial bodies as evidence. Minnesota's actual pregame notes are **4,645,244 bytes**, so one explicitly bounded 8 MB recovery was necessary. Its verified Last-Modified is **September 25, 2024 14:27:18 UTC**, before the Michigan game. Printed pregame notes support a projected Brosmer role, not a complete confirmed lineup or unrestricted participation.

Primary recovery included two official NFL inactive articles: [Buffalo](https://www.buffalobills.com/news/bills-list-5-players-inactive-vs-jaguars-week-3-mnf) published 2024-09-23 21:59 UTC, and [Jacksonville](https://www.jaguars.com/news/k000034-jaguars-in-and-out-2024-week-3-evan-engram-darnell-savage-out) published 22:00:23 UTC. They contain **12 inactive facts**, not proof that everyone else was healthy. Six official historical NBA PDF editions parsed **627 report rows**, which are not 627 distinct players or confirmed starting lineups. Independent official NBA books were recovered and checked against the existing event archive. Raw bodies remain private; source versions, derived results and exact model bindings are published.

## Source and mechanical certification

| League | Main source matchups audited | Complete accounting replays | Additional result |
|---|---:|---:|---|
| NFL | 12 | 12 | 9 source clock-boundary checks pass; 3 retain missing/corrected clock anchors |
| CFB | 12 after the fixed clock-fit cutoff | 5 | Only 1 source clock-boundary check passes; primary live-clock observations and administrative/penalty coverage remain incomplete |
| NBA | 18 | 12 | 15 official minute budgets reconcile; 12 have the complete source accounting needed for the mechanical subset |

An earlier eight-game CFB expansion was rejected because the fixed V21 clock was fitted **after** those games. The follow-up selects chronological inputs after the existing September 20, 2024 clock cutoff. No temporal check was disabled and no clock was tuned to scores. The regulation-only primary adapter is not applied across repeated untimed overtime clocks.

The [model-bound certificates and run results](V27_MECHANICAL_RESULTS_R2.json.gz) include exact model/configuration hashes, individual instance hashes, source editions, independent game IDs, generated-case checksums and check-by-check outcomes. Both NBA variants pass the **conditional mechanical subset** on 12 source-reconciled inputs: five-player seconds, scoring, rebound opportunities, substitutions/fouls and regulation/OT accounting. These are final-conditioned mechanics certificates, **not** approved pregame parameter sets, probability validation or permission to use current registry winners together.

NFL and CFB certificates remain partial. Pace/possession-distribution realism, complete timing regimes and OT coverage are not certified. NCAA anonymous attempts continue as unassigned TEAM credits. Source disagreements are retained, including NBA turnover/shot attribution and rebound differences; they were not forced to match final totals.

Reporting corrections are explicit: the stage-1 manual clock tally of 8 NFL / 0 CFB was wrong; the verified tally is **9 / 1**. Initial mechanical report R1 also used exact floating-point equality for NBA seconds. R2 uses the **existing ledger tolerance of 1e-7 seconds**, rejects one-second errors, and leaves every simulation unchanged. Earlier files remain available for audit.

## Bounded NFL clock experiment

The tested phase clock increased total play volume because the old kind-only pool mixed stopped incompletions with completed passes carrying between-play runoff. A new **disabled-by-default** NFL candidate conditions observed intervals on play kind, clock-stop regime and late-half state. It never substitutes a running-clock interval when the required stopped regime is absent. NCAA keeps its separate censored law.

| Variant / matched inputs | Prior phase-clock mean plays | Conditional-clock mean plays |
|---|---:|---:|
| Event reference, 12 matchups | 155.00 | 134.04 |
| Source-mean head adapter, 11 common matchups | 155.18 | 135.86 |

There were **46 completed candidate mechanics trials**. The Pittsburgh–Atlanta specialized case was withheld for missing same-kind/same-stop support. Paired game-level intervals for the **play-count change** are in the artifact; they are not accuracy intervals. These laws use final-conditioned historical inputs, and two trials per case cannot certify predictive distributions. The candidate is not enabled or promoted. A real-input seeded comparison verified the complete result is exactly unchanged when the candidate is disabled.

The main recorded runs completed 224 baseline, 108 phase-clock, 24 expanded-NBA and 46 conditional-NFL games. Two additional trials checked disabled-candidate equivalence. A failed preparation run retained 32 CFB trials; four NBA trials returned before a serialization failure and have no saved aggregate, so they are excluded from certification. All are mechanics work, **zero** are 10,000-trial qualified forecasts. The cumulative 512-game research cap was not reached or reset.

## Existing specialized heads: actual prospective execution

The existing V24 bank now runs on a new NBA event, **Philadelphia at Chicago, November 8, 2026**. It selected ten numerical heads: rolling-five references for minutes, points, assists, blocks, turnovers and shot opportunities; the existing conditional **Lasso rebound** candidate; and the existing conditional **hierarchical steals** candidate. No model was refitted or added to the registry. See [exact head versions and eligibility](V27_HEAD_USAGE.json).

Current roster validation admits **13** of 25 earlier-history participant heads and withholds the other 12. The retained minute means sum to **174.93 Chicago / 143.60 Philadelphia**, rather than 240. The remaining roster entries include reserves and players without these earlier heads; they are not automatically called active. Without a complete rotation/participation law, stretching those marginals to 240 would conceal missing evidence. Joint integration is correctly withheld. Marginal distribution compatibility and independent joint probability validation remain unestablished.

The new shadow harness initially selected a football team-4 roster for NBA team 4. That **R1 is invalid for evaluation**, is retained with [an explicit invalidation record](V27_BANK_R1_INVALID.json), and was corrected using league-qualified URLs plus exact team ID/name checks. [R2](V27_BANK_SHADOW_R2.json.gz) is a separately timestamped pregame revision. The three rolling-reference captures and all V26 forecasts were unaffected.

## Additional immutable prospective captures

| Game | Capture, November 7 UTC | Conditional score reference, away–home | Qualification |
|---|---|---|---|
| Cincinnati at Atlanta, Nov 8 14:30 UTC | 00:55:16 | 27.4–24.5 | Full availability, participation, joint pace and probability evidence missing |
| Arizona State at UCF, Nov 14 | 00:55:19 | 27.6–27.8 | Provider lists **TBD**; 05:00 UTC is a placeholder, not verified kickoff. Same full-game blockers apply |
| Philadelphia at Chicago, Nov 8 20:30 UTC | 00:55:23 | 121.2–106.8 | Current roster exists; complete active lineup/rotation and distribution validation missing |

These [three immutable references](V27_PROSPECTIVE_R1.json.gz) cover **55 players**. They reuse the existing simple arithmetic reference, not a certified joint simulation. No unsupported win, spread, total or prop probability, prediction interval, price, fee or CLV was invented. Every V26 target was excluded both as a new target and as historical input. [Exact per-game qualification](V27_QUALIFICATION.json) keeps the TBD and other blockers explicit.

The existing postgame grader was reused with an explicit V27-only input set. Its safety run made **zero final-stat requests**, retrieved **zero final games**, and kept all three pending. The invalid bank R1 is excluded; the valid bank R2 means have a frozen grading adapter. Grades will remain conditional point-error measurements; they cannot establish joint-model superiority or calibration where no distribution was forecast.

```bash
# Run only after results exist; never regenerate the saved forecasts.
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python scripts/v27-grade.py --id postgame-v27-r1
```

## Remaining gates and decision

| Blocker | NFL | CFB | NBA |
|---|---|---|---|
| Complete point-in-time starters / availability / restrictions | Partial inactive facts; no complete forecast input set | Projected QB notes; incomplete injury/participation history | Current roster plus dated reports; confirmed game-specific rotations missing |
| Source consistency / rules / pace | Three clock-anchor cases unresolved; clock candidate remains diagnostic | Administrative clocks, penalties, source gaps and season/OT coverage incomplete | 12 conditional accounting cases pass; six attempted sources remain incomplete |
| Actual specialized joint distributions | No eligible joint distribution certificate | Clock/participant blocks remain | Current marginal participant/minute coverage fails; no forced reconciliation |
| Independent joint probability evaluation | No qualified cohort | No qualified cohort | No qualified cohort |

The existing probability gate requires two distinct, unprotected, prior validation windows of at least 30 games with calibration/coverage evidence. No such new cohort is claimed. No Brier, log loss, CRPS, coverage or accuracy improvement is fabricated from mechanics. The archived 79-game sealed set and locked cohorts remain protected. The November 9 V26 grading is not used for tuning these snapshots or making broad superiority claims.

Stop condition: the bounded experiments found specific source and opportunity blockers, and the remaining strict gates cannot be resolved with the recovered evidence. No unattended simulation campaign is running. Further work needs verified game-specific active personnel/rotation inputs, broader rule/pace source coverage and genuinely independent frozen joint forecasts. Production and all existing champions remain unchanged.

## Executed verification and resources

Final checks passed **570 Python tests**, **795 TypeScript tests**, and **typecheck**. Source hashes were unchanged across the final full Python run. Earlier focused passes covered evidence, source readers, ownership binding, model-bank links, clock regimes and ledger roundoff. These are software checks, never an accuracy claim. [Executed receipts](V27_SOFTWARE_CHECKS.json) identify command scope and timing.

The five completed controlled mechanics/source jobs used **70.56 measured CPU seconds** and peaked at **2,267,584 KiB RSS**. Their artifacts contain 402 completed mechanics trials, plus the separate two-game disabled-candidate equivalence check and the explicitly retained partial preparation results. The final Python suite used **161.84 CPU seconds**, TypeScript **48.90**, and typecheck **6.88**. An earlier full Python pass and engineering/source probes consumed additional time; these selected receipts are not presented as the entire session's total. [Resource receipts](V27_RESOURCE_RECEIPTS.json) preserve those distinctions. No experiments ran on Vercel or the Render frontend, and no paid resources were created.
