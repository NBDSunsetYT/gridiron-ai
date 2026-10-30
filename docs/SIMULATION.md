# Play-by-play research simulator

This is an **unvalidated conditional empirical play-resampling baseline**, not a
claim of professional oddsmaking accuracy. No historical NFL dataset is bundled.
There are no embedded team strengths, injury multipliers, or generated production
results. Fit with authorized historical evidence before running any games.

## Run the separate service

```sh
python -m venv .venv
. .venv/bin/activate
pip install -r modeling/requirements.txt
# Set a random secret of at least32 characters in your server environment.
# Never put this secret in a NEXT_PUBLIC variable or in browser code.
uvicorn modeling.service:app --host 127.0.0.1 --port 8000 --workers 1
```

Configure the Next server with `SIMULATION_SERVICE_URL=http://127.0.0.1:8000`
and the matching `SIMULATION_SERVICE_TOKEN`. On separate hosts use a private
network and HTTPS. Do not publish this service directly to the Internet. The
service has no user accounts: the authenticated Next proxy owns authorization,
persistence, request limits and each user's job history. It accepts only one
CPU-bound fit/simulation at a time and returns429 while occupied.

`POST /fit` and `POST /simulate` require `Authorization: Bearer <server token>`.
The fit result includes an HMAC-signed model artifact; simulate rejects changed
artifacts. Changing the token invalidates signatures, so keep your raw training
CSV and refit after rotation. GET `/health` reports readiness without secrets.

For a local offline research process without FastAPI, provide JSON on stdin to:

```sh
python -m modeling.simulator < request.json > result.json
```

CLI requests support `action:"fit"` with CSV/source/asOf, or a simulation body.
The CLI trusts the artifact you supply and does not verify its service signature.

## Historical input schema

Supply a normalized UTF-8 CSV, not a sportsbook screenshot. All data must have
been available strictly before the declared `asOf` timestamp. Do not include
future game plays. The fitter rejects duplicate play IDs and post-cutoff rows.
The source field must describe the data source and permitted usage. Software
cannot verify that a user-supplied source is authentic or licensed.

Required columns:

| Column | Meaning |
| --- | --- |
| game_id, played_at | Unique historical game ID and timezone-aware historical play timestamp |
| offense, defense | Stable team identifiers, distinct |
| down, yards_to_go | Down1–4; positive distance to gain |
| yardline_100 | Distance from offense to opposing end zone,1–99 |
| seconds_remaining | Historical regulation game seconds remaining,0–3600 |
| score_diff | Historical offense score minus defense score |
| play_type | pass, rush, sack, punt, field_goal, kneel, spike, extra_point, two_point |
| yards_gained | Actual offensive net play yards; negative losses |
| elapsed_seconds | Observed play plus runoff time,1–90 |
| drive_start |1 when this play starts an offensive drive; otherwise0 |
| complete_pass, interception, fumble_lost | Binary0/1 indicators |
| field_goal_made |0/1 kick success; also conversion success for extra_point/two_point rows |
| punt_yards, turnover_return_yards | Observed punt and opposing return distances |
| passer_id, receiver_id, rusher_id | Stable player IDs; empty only when not relevant |

Optional `play_id` is strongly recommended. `availability` can contain JSON such
as `{"player-123":"active"}` with statuses `active`, `limited`, `inactive`.
These must describe the **historical game context**, not today's reports. The
fitter rejects inactive players participating in a play. To condition a defense
injury, label the defensive player's status on the opposing offensive plays too.

At least four historical games, two teams with100 plays each, three plays at
each down, four drive starts and five conversions per selected offense are
required. These are computational evidence gates, **not proof of statistical
adequacy**. Sparse sources and small injury cohorts can still be highly biased.
Input cap:20MB CSV/100,000 plays per artifact. Partition a larger warehouse into
explicit fit windows. The service JSON request cap is25MB, which can be reached
before the row cap after normalization; use smaller explicit fit windows.

## API bodies

Fit:

```json
{"csv":"...normalized CSV...","source":"Source URL / license and extraction date","asOf":"2025-09-01T00:00:00Z","teamMinPlays":100}
```

Simulate:

```json
{
  "model":{"...":"signed model returned by fit"},
  "home":"TEAM_A",
  "away":"TEAM_B",
  "eventStart":"2025-09-10T00:00:00Z",
  "simulations":10000,
  "seed":42,
  "postseason":false,
  "contracts":[
    {"id":"exact-contract-id","kind":"player","playerId":"player-id","stat":"receivingYards","threshold":64.5,"direction":"over","equality":"no"}
  ]
}
```

Standard10,000, Advanced50,000, Research100,000 and custom1,000–100,000 runs are
supported by the HTTP service. The CLI permits smaller mechanical tests.

Contracts support home_win, spread (home minus away score), total, team_total
(with `team:home|away`) and player outcomes. Direction is over/under. Exact
threshold equality must be `yes`, `no`, or `push`. Player stats include passing
attempts/completions/yards/TDs/interceptions, targets, receptions/receiving
yards/TDs, carries/rushing yards/TDs, and `touchdowns` (rushing+receiving).
Home-win ties follow the explicit equality rule, defaulting to push. The
contract adapter must map its exact yes/no/refund settlement semantics.

`probability` is unconditional yes outcomes divided by all simulated games.
`pushProbability` is separate. Use exact contract refund/settlement rules rather
than interpreting conditionalNonPushProbability as an unconditional contract
price. `jointOutcomes` contains aligned contract outcome combinations and counts;
it preserves within-game correlation without independently multiplying legs.

## What the engine models

The state includes possession, field position, down, distance, game clock,
score, halves and overtime. Each play is sampled as one linked historical event
conditional on offense, defense, down, field zone, distance band, score state and
late-game clock. Sparse contexts back off to offense/down pools. Every backoff
level is counted in the result. No team strength is invented when evidence is
missing. The first possession is a fair coin. Second-half reception reverses it.

Passer attempts/completions/yards and receiver targets/receptions/yards come
from the **same play**, so yardage and touchdown identities remain linked.
Rushing opportunities and touchdowns likewise arise from offensive events.
The engine transitions punts, field goals, sacks, interceptions, fumbles,
turnover returns, downs, touchdown conversions and safeties. Red-zone behavior,
fourth-down decisions and clock duration come from selected historical pools.
Regular-season overtime uses a10-minute period and both teams get a possession;
postseason uses15-minute periods until a winner, with an eight-period safety
limit. Defensive return scores end overtime. Mechanical rules still require
validation against real NFL histories before trusted deployment.

A confirmed scenario can be passed as
`"scenario":{"playerId":"id","status":"inactive"}`. It selects actual labeled
historical contexts and reruns every game; insufficient comparable evidence is
rejected. It never simply scales a quarterback or receiver by an invented
multiplier. **Calibrated availability mixtures, causal lineup adjustment,
weather fits and future roster projection remain incomplete.**

## Uncertainty and evidence limits

Outputs include win/tie probabilities, scores/margins/totals, player histograms,
90% simulated outcome ranges, exact contract probabilities, joint outcomes,
Monte Carlo standard errors and convergence checkpoints. Wilson95% intervals
measure **sampling error conditional on this fitted artifact**. They do not
measure source quality, model misspecification or player availability uncertainty.
`uncertainty.modelInterval` is deliberately null: parameter/bootstrap model
uncertainty has not been estimated. More iterations do not repair that absence.

Penalties, timeouts, replay, special-team return fumbles, detailed formations,
coach policies, weather and future roster changes are not yet modeled. Historical
elapsed time approximates clock management; it is not a strategic timeout model.
Team/down fallback can discard defensive/score/field-position context. Opponent
strength and injury effects are observational, not causal. These limitations
must accompany displayed projections.

## Verification

```sh
python -m unittest modeling.test_simulator -v
```

The committed test fixture is labeled **SYNTHETIC MECHANICAL TEST ONLY** and is
created inside tests, never seeded into production. Tests execute10k/50k/100k
complete game paths, correlated passing/receiving statistics, exact threshold
settlement, evidence gates, fixed-seed reproducibility, leakage rejection and
sampling convergence. They are not an accuracy backtest. A separate preliminary audit now uses actual public NFL2023 play-by-play:
see docs/NFLVERSE.md and docs/reports/simulation-backtest.json. Its four held-out
games do not establish calibration or model superiority. The synthetic mechanics
tests and real historical audit must be described separately.
