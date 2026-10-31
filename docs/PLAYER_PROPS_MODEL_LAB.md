# Player-prop evaluation and model development

The automatic player-prop model is a research model. A valid simulation, a narrow Monte Carlo interval, or a good result on one historical game does not establish calibration or profitable market value. The retained historical home-win ensemble benchmark is a different target and cannot calibrate player props.

## Prospective archive

`shared_prop_snapshots` freezes the exact player, contract, threshold, side, input version, model version, original quote and prediction before kickoff. The database checks its own archive clock, rather than trusting a backdated JSON field. A non-null probability requires a matching completed full-game simulation. Withheld forecasts can remain null; they are not counted as successful predictions.

`shared_prop_quotes`, snapshots, outcome resolutions, model-artifact versions and run-result links reject updates and deletion. An updated quote creates another observation. Repeated research can link an existing immutable forecast into a new run without duplicating the historical probability or changing its original market price. Current quotes/valuations are separate response fields.

The new tables contain public football research only. Personal financial records, private imports and conversations retain their existing user ownership and row-level security. The public research capability cannot invoke a personal ledger operation. Verified manual contracts are rejected by the shared-contract writer and remain private.

## Final statistics and settlement boundaries

The scheduled model lab reads fixed public nflverse weekly player-statistic assets and the verified schedule. It requires the exact GSIS player ID, game ID, season, week, team and opponent. An actual final schedule result and full-game/overtime coverage must match the frozen contract rules.

A missing statistic is unavailable, rather than zero. Positive observed attempts, targets, carries, return or kicking activity can establish participation. All-zero activity does not establish an inactive designation. Unsupported participation or exceptional settlement conditions stay unresolved. Total touchdowns are not inferred by adding potentially overlapping defensive and fumble-recovery aggregates.

Statistical outcome comparisons are explicitly distinguished from confirmation of an exchange payout. The lab never settles a personal wager. The user records the actual settlement and payout in Wallet. Provider voids, unresolved fair-price exceptions and non-binary outcomes do not enter binary Brier/log-loss calculations.

A genuine source correction appends a new resolution referencing the prior one and a new source version. It never rewrites the forecast. An unchanged final statistic is not repeatedly recorded merely because the collection clock or a different player's data changed.

## Accuracy protocol

`lib/player-props/evaluation.ts` defines `prop-prospective-game-block-6.0.0`:

- Select the latest eligible pre-kickoff snapshot for each exact contract and model version, without looking at its outcome.
- Normalize YES/NO forecasts to the same YES target so complementary snapshots are not counted twice.
- Exclude retrospective imports, late archives, look-ahead inputs, ambiguous resolution corrections and unverified or voided outcomes; retain exclusion counts.
- Calculate Brier score, log loss, reliability buckets, expected calibration error and observed/predicted rates by category, model version and event date.
- Compare market and model scores only on the same contracts with supported original market probabilities. Missing prices or fee assumptions are not substituted.
- Use reproducible game-block bootstrap intervals to preserve dependence between props in the same game. Fewer than eight game blocks produces no bootstrap interval.

The public performance endpoint returns aggregates, not the full snapshot-ID lists or unbounded evaluation rows. Empty or inaccessible archives produce `Insufficient evidence` or `Data unavailable`, rather than invented accuracy percentages. Seven-day, 30-day and all-time groups use actual archived events.

## Controlled candidate development

Calibration fitting requires at least 200 eligible prospective observations, 40 games, 30 outcomes of each class and probability-range coverage in one exact category/model version. Supported methods are monotone isotonic regression and fixed-penalty regularized Platt scaling. A fitted object is a candidate, not an approved production calibrator.

A candidate is archived before validation forecasts. Its holdout is the **first 40 subsequent eligible game blocks**. Adding favorable later games cannot rescue a failed holdout. At least 100 covered predictions and 20 outcomes of each class are also required. Both paired game-block Brier and log-loss improvement intervals must lie below zero, calibration error must not regress, and both chronological halves must improve. If an approved incumbent exists, improvement is measured against that incumbent, rather than only the raw model.

Without a matching approved artifact for the category and underlying model version, `calibratedProbability` remains null. Out-of-range calibration extrapolations and malformed or mismatched artifacts are withheld. No historical home-win benchmark is substituted. Approval does not establish market advantage; that has a separate matched-market comparison.

After a completed rejected holdout, a later fit requires sufficient new data and a seven-day development cooldown. It receives a new immutable identity and a new subsequent holdout. A single incorrect forecast never causes retraining or promotion. Drift diagnostics queue review; they do not directly retrain, promote or settle a wager.

## Version selection and rollback

Candidate and approved rows are separately retained under the artifact's ID/status composite key. The default server selection uses the newest valid approved artifact for each category/model scope.

An operator can pin an older approved artifact or disable calibration for one scope through the optional server-only `GRIDIRON_PROP_CALIBRATOR_SELECTION` JSON configuration. For example, a key `receivingYards|pbp-conditional-4.0.0` can name an existing approved artifact ID; a null value disables calibration for that scope. An unknown or incompatible ID withholds calibration rather than silently selecting another model. This is an operator recovery control, not an end-user setup requirement. Existing predictions and model versions are never deleted during rollback.

## Executed historical audit

`python -m modeling.backtest_player_props --season 2026 --train-week 6 --heldout-week 7 --games 2 --simulations 10000 --out docs/reports/v6-player-prop-historical-audit.json` runs a fixed-cutoff study on actual published NFL play-by-play and weekly final statistics. It selects each team's historical prefix volume leader for passing, rushing and receiving, using predeclared thresholds of 199.5, 59.5 and 40.5 respectively. No heldout statistic selects a player or threshold, and no historical DraftKings price is invented.

The executed study contains two heldout games, 10,000 complete simulations per game and 12 matched player outcomes. Its Brier score is 0.1940738992 and log loss is 0.6774066951. **This does not establish calibration**: the sample is small, player outcomes are correlated, historical first-publication times are unverified, current source files were collected after the historical games, and injuries/weather were not fitted in this study. It is marked retrospective, creates no prospective database forecasts, leaves calibrated probabilities unavailable and promotes no model. See the full source hashes, timestamps, per-prediction results and exclusions in [the audit](reports/v6-player-prop-historical-audit.json).
