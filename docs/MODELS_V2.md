# Modeling, uncertainty, and evaluation

GRIDIRON AI calculates probabilities only from supplied evidence. An empty database means insufficient evidence, not an opportunity to insert plausible-looking numbers.

## Price arithmetic

For American odds `a > 0`, decimal odds are `1 + a/100`; for `a < 0`, they are `1 + 100/|a|`. Break-even probability is the reciprocal of decimal odds. For predicted probability `p`, expected return per unit staked is `p × decimalOdds − 1`, assuming a binary win/loss market with no push. Pushes, alternate settlement rules, dead heats, and promotional payouts need explicit treatment; do not silently apply this binary formula to them.

Fair odds are derived from probability rather than copied from a sportsbook. A high win probability can still have negative expected value when the price is expensive. Historical accuracy and edge are different measurements.

## Evidence and limitations

- User-entered observations must be real, relevant, and measured before the prediction timestamp. Check sample definitions, market settlement rules, and missing records.
- Fitted outcome distributions and empirical hit frequencies are baselines. They do not inherently account for usage changes, weather, injury news, coaching, selection effects, or schedule strength.
- Sampling intervals describe uncertainty under stated assumptions. They do not include every source of model misspecification.
- An input label does not verify provenance. Preserve source URL/name, acquisition timestamp, event time, and permission to use the data.
- Do not train on future outcomes, closing lines recorded after prediction, revised statistics unavailable at prediction time, or overlapping targets that leak across a split.

## Validation

Use chronological rolling out-of-sample evaluation. Fit preprocessing, feature selection, distributions, and calibration using only the training period. Freeze model version and prediction timestamp before outcome availability. Report the number of predictions, date range, market, Brier score, log loss, calibration by probability bucket, and intervals where supported. A small sample does not establish profitability or stable calibration.

The included tests verify mathematical behavior and failure handling, not future profitability. No league-wide model performance is claimed without actual held-out records. Licensed historical feature ingestion, sophisticated hierarchical team/player forecasts, and continuous production retraining require additional data and development.

## Parlays

Independence is an explicit baseline, not a correlation correction. Same-game legs often share outcome drivers. A valid joint simulation needs aligned joint observations or a supplied positive-semidefinite correlation matrix with documented meaning and uncertainty. Correlation assumptions are not inferred from selections' names. In the absence of adequate dependence evidence, show insufficient evidence for joint probability and keep the independence estimate clearly labeled.

Theoretical product payouts may differ from a sportsbook's same-game parlay price. Compare against an actually quoted combined price when evaluating expected value. Adding legs changes both payout and joint failure probability.
