# GRIDIRON AI 14.0 — measured football simulation

This is an incremental upgrade of the existing Next.js/FastAPI application. It
preserves the existing NFL/CFB engines, PropLine reference feed, Supabase Auth,
owner-isolated financial records, combinations and iPhone PWA. No user data was
reset. The existing Render service remains the data gateway; Vercel hosts the
private quantitative service as well as the web app.

## What is implemented

- **Simulation vs. Reality** is a primary navigation destination for NFL and CFB.
  It compares frozen score, total, margin and player-stat distributions with
  sourced final observations; displays signed/absolute errors and CRPS; and
  overlays the actual result on the simulated histogram. Equal-tailed 50%, 80%,
  90% and 95% prediction intervals show whether the actual outcome was covered.
- A representative simulated game can be inspected play by play on a football
  field. Only up to three representative traces are retained, never all games.
- New complete-game public research is captured automatically. Existing NFL
  snapshots are recovered incrementally using their original database timestamp.
  A current import cannot become a pregame prediction by backdating JSON.
- Final research statistics come from the existing nflverse schedule/player
  releases and published ESPN CFB final box scores. Exact sport/event/player/team
  identities are checked. Missing statistics and unverified participation stay
  pending. College team-attributed rushing rows are not assigned player IDs.
- Final corrections append new actual-result and evaluation records. Frozen
  forecasts are never edited. A failed save never reports a completed archive.
- **Model performance** and **What GRIDIRON AI learned** use actual archived
  comparisons. Final pregame versions are selected per game and model; multiple
  snapshots are not independent games. Retrospective reruns are excluded from
  prospective reliability, calibration and training eligibility.
- GALL runs on the existing signed schedule, at most once hourly, with three
  forecast checks per sport per tick. It does not run on page visits. Future
  evaluations include compact sufficient statistics so aggregation avoids
  repeatedly downloading every player histogram. A complete-archive bound fails
  closed rather than presenting a truncated subset as all-time performance.
- The controlled home-win recalibration candidate requires 200 distinct pregame
  games and 40 weeks. It uses fixed regularization and chronological 60/20/20
  week partitions, two separate held-out tests, paired two-week bootstrap
  intervals and non-worse log loss. Only a successful candidate may become a
  separately displayed home-win calibration. It cannot replace player models or
  game mechanics. Promotion and rollback are append-only; future deterioration
  monitoring uses only forecasts that actually used that artifact.
- The private tool-using assistant can retrieve comparisons, performance and
  journals through `read_simulation_reality`. An OpenAI credential is still
  required for actual language-model generation; tool availability is not proof
  that live generation was tested.

## Original GAFIE model

`modeling/gafie.py` is an original, experimental conditional-transition model,
written for this project. It is not copied from an upstream simulator and does
not sample random final scores or independent player props.

1. Fit regularized multiclass play selection on historical states: down,
   distance, field position, time remaining, score, game-script interactions,
   offensive team and defensive team. NFL and CFB are fitted separately.
2. Test on later, disjoint historical games against a state-aware empirical
   play-calling baseline. No held-out outcomes enter classifier training.
3. At each simulated state, calculate learned play-call probabilities and
   restrict them to supported historical joint-event types.
4. Draw a supported joint play outcome with its real historical participants.
   The sport-specific state machine then updates possession, field position,
   down/distance, clock, scores and all player statistics together.
5. Aggregate complete-game score and player distributions, convergence evidence,
   correlations and representative traces. Save the model/input version, seed,
   environment and source provenance.

The baseline path remains unchanged unless this candidate is explicitly selected
by the research runner. This preserves existing prediction mathematics and
avoids multiplying consumer compute costs. A play-selection improvement alone
cannot promote the full-game model.

Real local research tests ran 10,000 complete GAFIE NFL games and 10,000 complete
GAFIE NCAA games. Both improved held-out **play-selection** log loss over their
comparison baseline. The tested **final scores did not demonstrate improvement**.
The CFB scoring error was substantial, including in the existing baseline. The
candidate remains unpromoted; no market edge or reliable full-game calibration
is claimed. Repeated/batched clocks in the CFB source are an observed quality
concern, not a proven causal explanation. Current personnel, coverage, weather
and injury effects without verified fitted evidence are not invented.

The larger proposed opportunity/coverage/season-evolution networks and adaptive
simulation allocation are **not validated production models**. Tracking,
route/personnel and availability data are incomplete. These requirements are
explicit research limitations, not completed capabilities.

## Storage, durability and recovery

Migration `20261104061515_football_reality_learning_refs.sql` adds one compact
reference table. It does not modify private account tables. RLS permits public
football reads; direct anonymous/authenticated writes are denied. The existing
server capability authorizes writes through an invoker RPC and a private,
fixed-search-path implementation. Update/delete triggers protect the archive.

Payloads use the existing private, compressed, checksum-verified research bucket
and optional configured Mongo outbox. NFL/CFB data and private finances remain
separate. Exact historical GAFIE fitted inputs are archived once as bounded
compressed JSON, with a SHA matching the frozen run manifest. These are training
events, not millions of simulated plays. A seed by itself is not sufficient for
replay: code, dependencies, configuration and exact fitted input must also match.

No MongoDB/R2 connection is claimed unless configured and verified. This release
uses the already-operational Supabase private object store for its tested runs.
Financial records and saved research have no automated deletion policy. Restore
uses existing encrypted backups and immutable object references; do not reset
the database or drop the new archive as a rollback. Roll back application code
or set the server feature flags to zero while retaining every record.

Storage investigation found Supabase near its 500 MB database allowance, while
the Vercel app and free Render gateway remained reachable. Non-destructive table
compaction recovered only about 1 MB and preserved all 28,660 shared prediction
IDs/checksum. That did not solve the existing live-data pressure. New research
uses small database references rather than duplicate full distributions. No
paid resources, billing settings or historical records were removed. The exact
account warning was not available, so account-wide Render/Vercel quota exhaustion
is not represented as diagnosed or fixed.

## Reproduce the real historical acceptance

```sh
python scripts/reality-historical-audit.py --out /tmp/audit/nfl.json
python scripts/reality-college-audit.py --out /tmp/audit/cfb.json
python scripts/gafie-historical-audit.py /tmp/audit/nfl.json --out /tmp/audit/gafie-nfl.json
python scripts/gafie-historical-audit.py /tmp/audit/cfb.json --out /tmp/audit/gafie-cfb.json
# Operator-only, with existing server credentials; never expose them to clients:
node --env-file=.env.local --import tsx scripts/verify-reality-storage.ts /tmp/audit/gafie-nfl.json
```

Source downloads are public, fixed provider locations; no manual statistics or
invented prices are inserted. Generated fitted inputs are temporary local files,
not Git content. Historical reruns are visibly retrospective. Production
read-back and idempotency reports are in `docs/reports/reality-*.json`.

The unchanged baseline was tested at 10,000, 50,000 and 100,000 complete NFL games:
about 4.0, 23.7 and 41.4 local CPU seconds respectively. Compact raw outputs were
about 233, 257 and 267 KB, with one representative trace and no full-run game or
play retention. The same-seed 10,000-game result reproduced statistical outputs
exactly. These local timings are not a Render/Vercel billing forecast.

## Method origins and boundaries

The open-source audit records repository licenses, inspected source hashes and
limitations in `docs/reports/football-open-source-audit.json`.

- [nflverse](https://github.com/nflverse/nflverse-data): attributed public
  historical data. Dataset-specific licenses must be checked separately from
  package licenses, especially derived tracking datasets.
- [nflfastR](https://github.com/nflverse/nflfastR): EP/WP/completion/YAC modeling
  references. Their output models are not silently substituted for a complete
  generative simulator or claimed to validate our player distributions.
- [nflreadpy](https://github.com/nflverse/nflreadpy): data loading/caching design.
- [nfl4th](https://github.com/nflverse/nfl4th): state-dependent fourth-down
  decision references; an optimal decision model requires its own utilities and
  validation, not merely a historical punt frequency.
- [NFLSimulatoR](https://github.com/rtelmore/NFLSimulatoR): empirical state-transition
  reference; resampling needs shrinkage, chronological validation and clearly
  bounded context coverage.
- [CollegeFootballData](https://collegefootballdata.com/) and the existing
  [SportsDataverse source](https://github.com/sportsdataverse/sportsdataverse-data):
  independently identified NCAA data. Licensed entitlements and source clock/
  participant coverage are not assumed.

PropLine sportsbook odds remain separately labeled. No authorized exact live
DraftKings Predictions contract feed or verified executable combination rules
have been established. No unrelated sportsbook line is presented as that feed.

## Feature flags

- `GRIDIRON_GALL_ENABLED=0`: pauses automatic learning work; archives remain readable.
- `GRIDIRON_GALL_PROMOTION=0`: withholds home-win calibrator promotion/application.
- Original GAFIE full-game candidates remain experimental regardless of these
  calibration flags. They require broader full-game distribution validation.

Install the existing HTTPS app from Safari → Share → Add to Home Screen. Mobile
browser emulation checks are not a physical-iPhone installation test.
