# CFB complete-game research protocol

The CFB engine is separate from the existing NFL transition/model protocol. NFL
`fit.py` and `simulator.py` remain unchanged. CFB artifacts require `sport=CFB`,
CFB-prefixed team/player identities and model version `cfb-pbp-empirical-8.0.0`.
An NFL artifact cannot be substituted for a CFB model.

## Automatic source

The private worker retrieves the publisher's fixed public ESPN-derived CFB
Parquet release from the [SportsDataverse data repository](https://github.com/sportsdataverse/sportsdataverse-data/releases/tag/espn_cfb_pbp).
The repository publishes an [MIT licence](https://github.com/sportsdataverse/sportsdataverse-data/blob/main/LICENSE).
This path does not access a protected CollegeFootballData API or use a vendor key.
The source file, SHA256, retrieval time and actual historical play timestamps are
retained. Historical publication availability is unknown and stays null.

Only selected columns are read with PyArrow, then the two verified ESPN teams
plus actual CFB league two-point attempts are retained. Download size is capped
at 80MB, the disk cache contains one asset, and one fitted model is cached for
ten minutes. The source cache expires after six hours. No full-season 400-column
Pandas frame is constructed. Game/athlete identities come from actual source IDs;
names are not fuzzy-matched to produce participants.

Incomplete games, event times at/after the fitting cutoff, missing identities,
negated/unsupported plays and unsupported clock data are excluded and counted.
Observed turnover field-position changes preserve interceptions even when air
yards or individual return yards are unavailable. Missing return-yard statistics
are not turned into player return projections. Published penalties and rare
special-team events remain outside the supported baseline and limit its accuracy.

## Private HTTP routes

All routes use the existing server-only `SIMULATION_SERVICE_TOKEN`.

- `GET /cfb/status`: installed capability; does not claim a default trained model.
- `POST /cfb/public/prepare`: verified future game → source retrieval, normalized
  evidence and actual fitting readiness. No Monte Carlo games run here.
- `POST /cfb/public/analyze`: same game → actual fitted baseline and 10,000,
  50,000 or 100,000 complete coherent games. Default is 10,000.
- `POST /cfb/fit` and `/cfb/simulate`: preserved advanced signed-artifact protocol
  for authorized normalized CFB evidence. Normal application use calls the public
  research adapter, not a CSV upload.

Automatic input is `{game, simulations?, seed?}`. A game contains canonical
`id: cfb:espn:<eventId>`, explicit `espnGameId`, source `season`, future
`startTime`, and `home`/`away` objects with canonical `id` and explicit `espnId`.
The frontend never supplies a source URL, credential, invented statistics or a
model-confidence value. Live/completed games are rejected as new pregame analyses.

Prepare returns `{sport:'CFB',ready,inputHash,modelVersion,engineVersion,
rulesVersion,training,research,limitations}`. Ready means sufficient actual
empirical coverage, not validated calibration. Analyze returns
`{status:'completed',sport:'CFB',game,simulations,inputHash,result,research}`.
Result includes exact score/player frequency histograms, convergence, Monte Carlo
intervals, source evidence and separate game-block parameter sensitivity.

Transport errors return 503 with `source_unavailable`, not an empty market list.
Insufficient historical coverage returns 422 without a replacement probability.
Synthetic artifacts cannot produce forecasts on Vercel or Render; isolated
mechanical tests opt in locally through a non-client environment flag.

## NCAA rules and supported statistics

The [official 2026 NCAA rulebook](https://ncaaorg.s3.amazonaws.com/championships/sports/football/rules/PRMFB_RulesBook.pdf)
was retrieved and hashed (`2a9e63b038b6efc70ad846487f33fdda175993c2229c911c3e06291ec74a9dd5`).
[2026 amendments](https://ncaaorg.s3.amazonaws.com/championships/sports/football/rules/2026PRMFB_2026RuleChanges.pdf)
and the [statistics manual](https://fs.ncaa.org.s3.amazonaws.com/Docs/stats/Stats_Manuals/Football.pdf)
were checked independently.

The protocol models four fifteen-minute quarters, preserved possession at quarter
boundaries, halftime possession, scoring, downs, realistic sampled play selection,
field position, punts, previous-spot missed field goals, turnovers and dynamic score
contexts. NCAA sacks count against quarterback rushing attempts and rushing yards.
Passing yards and receptions emerge from the exact same sampled passing events.

Tied regulation games use paired untimed possessions from the opponent's 25-yard
line in overtime periods one/two. Touchdowns in period two require a two-point
attempt. From period three the model alternates two-point attempts from the
three-yard line; those attempts do not inflate ordinary player statistics.
Unneeded walk-off tries are omitted. Conversion outcomes require actual CFB
evidence; no arbitrary success percentage is inserted. Unresolvable or inadequate
evidence raises an error rather than manufacturing a winning team.

Timeout/replay administration, rare one-point try safeties, defensive try returns,
kickoff-return touchdowns, blocked-kick returns and fair-catch kicks are not fully
modeled. Tempo uses observed CFB game-clock deltas, including genuine zero deltas.
Historical conditional game scripts influence opportunities, but current depth
charts, injuries, transfers, independent talent/SOS coefficients and weather
effects are incomplete. Outputs remain explicitly conditional and uncalibrated.

## Executed verification

- Mechanical fixtures: complete 10,000/50,000/100,000-game modes, coherent player
  statistics, NCAA scoring/overtime, stopped clocks, identities and source cutoffs.
- Private route tests: authentication, signed-artifact integrity, NFL/CFB isolation,
  missing-evidence withholding and production rejection of synthetic forecasts.
- Source-normalization tests: explicit participants, current/future cutoffs,
  incomplete games, conversion accounting, missing IDs and distinct source outages.
- Actual verified future BYU at Utah game `401856849`, November 7, 2026: 10,000
  complete games from actual historical CFB plays; all score/player histogram
  counts and shared passing/receiving totals reconciled. Local end-to-end time
  8.159s; peak resident memory 250.21MB. This is not a hosted or physical-phone test.
- Four actual latest completed source games: an event-chronological retrospective
  reconstruction produced Brier **0.3913260825** and log loss **1.0894075175**.
  The weak, tiny pilot is retained and **not promoted**. Historical publication
  availability, prospective calibration and market superiority are not established.

See `docs/reports/v8-cfb-actual-10000-games.json` and
`docs/reports/v8-cfb-historical-audit.json`. Increasing simulation count reduces
sampling noise, not model error or missing availability evidence.

The independent parameter bootstrap includes all actual CFB historical game
blocks that contribute the league two-point fallback pool, as well as the
selected teams' games. For the verified BYU/Utah capture this was 182 total
blocks and 14 selected-team blocks; its broad interval is sensitivity, not
calibrated forecast coverage. The primary 10,000-game estimate is unchanged by
this separate uncertainty calculation.
