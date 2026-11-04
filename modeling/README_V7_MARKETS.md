# Full NFL event-contract research, version 7

Version 11 storage update: new runs replace the ordered `gameSamples` described
below with per-replicate joint `gameHistograms` of home score, away score and
frequency. Threshold intervals preserve the same counts and settlement rules.
The legacy binary encoding remains readable. See `docs/GRIDIRON_V11.md`.

The existing empirical play-by-play simulator still produces coherent complete
games in 10,000, 50,000 and 100,000 modes. The v7 additions do not replace its
conditional play-selection or create independent player guesses. Player events,
team scoring, overtime, margins and totals emerge from the same game. Historical
cohorts, game scripts, down, distance, field position and clock remain the inputs.

## Exact supported game markets

`game_research.evaluate_exact_game_distribution(result, definition, outcome)`
reads exact integer frequencies for game winners, spreads, combined points and
team points. It never multiplies independent team-score marginals to reconstruct
a total or margin. Definitions require explicit tie/equality settlement and
verified full-game including-overtime coverage. Regulation, half and quarter
outcomes cannot be inferred from final-score histograms. Explicit overtime
exclusions are rejected before expensive simulation work on every compute route.

`home_win` and `away_win` are separate events. An away win is not simply a home
loss if a tie has a separate payout. The helper retains YES, NO and push counts;
integer thresholds use the contract's explicit equality rule, not an assumed
traditional sportsbook refund. `spread` uses **home minus away** coordinates.
An away contract must have its threshold and direction explicitly normalized.
`team_total` requires the exact home/away team identity. These research helpers
do not establish an exchange's exceptional or partial-payout settlement rules.

## Shared whole-game parameter samples

`uncertainty.parameterBootstrap.gameSamples` supplements the preserved player
samples with the scores from the identical independent parameter games. Encoding
is `gzip_base64_int32le_shared_game_scores_v1`, value type signed little-endian
int32, shape `[replicates, gamesPerReplicate, 2]`, and team order `[home, away]`.
Coverage is explicitly `full_game_including_overtime`. Dimensions, byte counts,
team identities, bounded decompression and historical game-block counts are
validated before reading. The automatic configuration stores 10 × 100 whole
games, only 8,000 raw score bytes, without simulating additional games.

`parameter_game_interval` evaluates a newly requested threshold in each fixed
replicate. Increasing the main simulation count does not narrow this independent
sensitivity interval. These samples include finite inner-run simulation noise;
they do not measure all structural or future injury uncertainty, and they have
no validated predictive coverage. Older v6 results without score samples return
unavailable sensitivity instead of inventing it from marginal confidence bands.

## Injuries, weather and calibration

The existing pipeline can condition a supported availability scenario on actual
labeled historical games. Unknown availability does not receive an invented
active probability. Unsupported multiple-injury cohorts, arbitrary snap or
target-share multipliers, and unfitted numerical weather effects remain withheld
or explicitly unadjusted. Source invalidation and the new pipeline version cause
relevant automatic game jobs to refresh while preserving old snapshots.

Raw frequencies stay separate from prospective calibrated probabilities. No v7
calibrator is approved merely because this implementation or one backtest ran.
Displayed percentage prices, fees, cancellation, non-participation and actual
payout rules must be verified by the market layer; missing evidence withholds
fee-aware value. DraftKings Predictions is never treated as DraftKings Sportsbook
or silently replaced with another exchange.

## Prospective game-contract auditing

The separate server module `lib/player-props/game-performance.ts` audits stored
game-contract predictions against published final NFL scores. It validates the
frozen game, team, exact operator/threshold, settlement rules, input timestamps
and database archive time before kickoff. A source's collection clock is not an
event timestamp. The six-hour maturity boundary applies before scoring.

The outcome is explicitly the **selected side's full 100-cent payout under
normal completion**. A 50-cent tie payment is not a full hit for either side.
NO forecasts are scored against their own target; neither their prediction nor
their final outcome is automatically replaced with one minus YES. These research
resolutions do not confirm an exchange payout or settle a private financial
position. Partial-tie prices cannot establish full-hit market-implied probability,
and unknown fees or unsupported terms withhold the market benchmark.

Background reconciliation appends source-version corrections with a linked audit
chain, confirms idempotent database writes, and caches aggregate Brier, log loss,
calibration diagnostics, game-block intervals, and category/model/date/time-window
reports. Interactive reads retrieve only that bounded aggregate. Missing or stale
audits remain unavailable or timestamped stale. No game calibrator is fit or
promoted by this module, and private ledgers and personal records are untouched.

## Reproducible actual-game audit

`python -m modeling.backtest_game_markets INPUT.csv.gz --train-week 6
--heldout-week 7 --games 4 --simulations 10000 --out REPORT.json` uses a fixed
chronological prefix, the first heldout games by recorded source time, and five
predeclared research definitions for every game. Final score fields must agree
and include an actual END GAME marker. Outcomes are read only after forecasts.
The report preserves input SHA-256, cutoff, definitions, selected game identities,
raw forecasts, score-count reconciliation, Brier score, log loss and calibration
diagnostics. Confidence calculations resample whole game blocks.

The executed v7 report contains four actual games and twenty correlated research
outcomes. Brier score **0.2896930985** and log loss **0.8011373769664702** do not
establish useful calibration or market superiority. Historical first-publication
times are unknown, and the thresholds are predeclared examples rather than
fabricated DraftKings contracts or prices. The report is explicitly retrospective,
not production eligible, and **NOT PROMOTED**. No private financial data or
prospective prediction records were modified by this audit.
