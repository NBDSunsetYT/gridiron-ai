# Version 12.1 — automatic probabilities and market comparison

The existing NFL/CFB application is upgraded in place. The complete-game engine,
private ledger, authentication, conversations, saved combinations and PWA remain.

## Consumer workflow

Open Props. Research starts automatically. Completed estimates sort highest first;
pending/stale records follow. Cards expose the independent estimate, quoted market
break-even before fees, their percentage-point difference, method, uncertainty,
quote/model times and availability coverage. Neither a large difference nor a high
hit rate establishes positive after-fee value. Missing prices do not hide supported
independent estimates. Missing model evidence is never replaced by market odds.

Sorts include probability, verified after-cost ROI, model–market difference,
quantified conditional model uncertainty, model update time, kickoff and name.
Missing costs and unknown model uncertainty are not replaced by probability or
Monte Carlo precision. Filters include today, tomorrow, upcoming and exact
sport-specific matchups. Local-calendar day filters respect the device timezone,
including DST. Grouped matchups expand/collapse and preserve their internal sort.

Signed-in view preferences use the existing owner-scoped Supabase preferences
endpoint. A non-sensitive browser mirror queues unsynced preferences; guests can
retain local view settings. Account/sport identities are isolated. Private records
remain server-backed and excluded from service-worker caching.

## Statistical evidence hierarchy

1. Current coherent complete-game simulations remain preferred. All related player
   statistics emerge from shared simulated plays; 10k/50k/100k meanings are unchanged.
2. A separate partial-pooling player-stat CDF can support missing player/stat
   distributions. Its role-cohort base is fitted from prior-season weeks 1–8;
   prior-season weeks 9–18 select pooling strength and history window. The current
   season is a chronological holdout. Base distributions are Student-t/normal for
   signed yardage and negative binomial/Poisson for counts. Exact numeric thresholds
   use a discretized CDF and strict inequality, including integer push mass.
3. Verified current/previous-season historical frequency remains available with
   explicit sample size and a wide Wilson interval if no distribution candidate
   qualifies. One recorded player game is supported; no five-game cutoff remains.
   These historical rates are not calibrated next-game forecasts.

Candidate publication requires a held-out paired-game bootstrap Brier improvement
and no log-loss deterioration. The fixed hypothesis families are 52 NFL stat/role
combinations and 13 CFB usage-role combinations. Bonferroni-adjusted one-sided
bootstrap p must pass 0.025; the other 0.025 is reserved for recalibrator testing.
5,000 bootstrap replicates are used. Prior strength/window are never fitted on the
held-out season. Retrospective conditional player-stat validation is not prospective
contract accuracy, historical executable-price validation or market superiority.

Earlier-season regularized Platt recalibration is implemented and separately gated
against the raw model on the independent holdout. It is applied only inside its
verified probability range, with approximate calibration parameter uncertainty kept
separate from Monte Carlo sampling error. **No tested real-data recalibrator passed
this release's gate.** No raw estimate is consequently called calibrated.

Source coverage uses nflverse current/previous weekly totals, current stable roster
crosswalks, available snap counts, practice/injury reports, depth charts and team
statistics. Future scheduled-game IDs are excluded from historical NFL inputs.
CFB uses separate current/previous SportsDataverse assets, exact ESPN identities,
completed regular-season stat events, overtime and NCAA sack rushing. Missing CFB
participant/stat coverage invalidates the affected statistic cohort, not unrelated
stats. Seasons have separate temporary cache paths.

Team/role changes, incomplete current availability, coaching and weather effects
remain structural limitations where an independently validated effect is absent.
Actual restrictions withhold unsupported availability. No arbitrary efficiency or
weather multiplier is applied. A conditional Bayesian interval is not a full model
risk interval. Even a historical rate of 100% is not a guarantee.

## Market identity and arithmetic

PropLine rows remain sportsbook references. American and decimal price break-even
are calculated separately from event contracts. Event-contract comparison requires
actual acquisition cost and payout terms; after-fee break-even also requires known
entry/winning fees. A displayed percentage or multiplier alone never establishes
those terms. Exact authorized DraftKings Predictions prices remain unavailable.

## Durable history and efficiency

Existing append-only automatic research versions are reused. Two non-destructive
migrations add a bounded capability-gated history reader/index and a snapshot
preflight. No user/financial table is reset, renamed or migrated.

The history chart reads exact sport/event/player/market/threshold/side/book snapshots,
with model/input versions, original prices and update reasons. Pagination retains
older history. Equivalent numeric threshold formatting does not break identity.
Ambiguous selections are withheld. Past predictions are never overwritten.

The existing queue keeps stable job IDs across the upgrade. Changed inputs invalidate
current results while old versions remain. Prices are excluded from model-input keys.
Unchanged distributions reuse immutable objects, with successful revalidation time in
small job metadata. Quote timestamp heartbeats do not create duplicate prediction
payloads; actual model/input/price changes remain separate snapshots. Atomic leases,
input-change fencing, backoff and existing compute/storage guards remain in force.
Only compact distributions, assumptions and references are stored permanently.

## Recovery and release checks

A Git checkpoint precedes the upgrade. Roll back the application deployment first
if necessary; keep all existing history, financial rows and additive indexes.
The history-reader migration changes no records. The preflight migration can be
reverted to the prior function implementation after rolling back the app; do not
drop version tables or delete research objects as part of rollback.

Reports in `docs/reports/props-v121-*` record actual tests and deployment status.
The source ZIP does not execute a backend on an iPhone. Open the hosted HTTPS URL
in Safari and choose Share → Add to Home Screen. Physical device installation is
reported separately from browser viewport testing.
