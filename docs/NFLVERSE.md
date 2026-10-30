# Local historical play-by-play adapter and preliminary audit

`modeling/nflverse_adapter.py` consumes a local nflverse CSV or CSV.GZ. It does
not download data or assert that every upstream field is licensed for every
purpose. Review the original release and source terms before use or redistribution:
https://github.com/nflverse/nflverse-data/releases/tag/pbp . The application
bundles code and an aggregate audit, not the raw historical dataset.

```sh
python -m modeling.nflverse_adapter /path/play_by_play_2023.csv.gz \
  --max-week 12 --out /tmp/normalized-pbp.csv
python -m modeling.backtest_simulator /path/play_by_play_2023.csv.gz \
  --train-week 12 --heldout-week 13 --games 4 --simulations 10000 \
  --out docs/reports/simulation-backtest.json
```

The adapter maps source `run` to rush, passing sacks to sack, and explicit
conversion events to their own types. Player identifiers, target/reception
links and outcome fields come from the original play rows. `time_of_day` is
retained as actual source event time; missing times are excluded. The program
never invents publication or kickoff timestamps. The audit uses the earliest
recorded source event for each held-out game and labels that meaning explicitly.

Elapsed clock is the next observed decrease within the same game half, searching
up to five subsequent source rows. This approximates historical runoff rather
than estimating a strategic timeout model. Penalties, laterals, non-offensive
kickoffs, unknown durations and unsupported rows are excluded with counts. This
filtering can bias scoring and play volume. No injury labels, weather or future
roster status are fabricated; those fields remain unavailable.

The committed aggregate audit fits regular-season weeks1–12 of real NFL2023
play-by-play and evaluates the first four games of week13 at a fixed chronological
cutoff,10,000 complete simulated games per matchup. It reports observed final
scores, mean simulated scores, Brier/log loss, score error, source hash and
backoff counts. The sample is much too small for claims of calibration, stable
performance or beating market prices. No model is promoted on this evidence.
The separate large game-total baseline audit is a different model and must not
be presented as validation of the play-by-play simulator.

Source data is treated as user-supplied evidence. An event timestamp is not a
publication timestamp. This preliminary audit lacks independent data integrity
verification, market benchmark prices, roster corrections, calibrated injury
mixtures and parameter uncertainty. Use the reports to identify defects before
any decision support; do not interpret10,000 iterations as10,000 independent
historical games of validation.
