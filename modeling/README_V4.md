# V4 model suite and enhanced complete-game research

The earlier empirical play-by-play artifact version remains supported. New fitting
options create `pbp-conditional-4.0.0` artifacts. The separate home-win suite is
`nfl-home-win-suite-4.0.0`; it does **not** forecast player props.

## Actual chronological game-outcome models

`advanced.py` trains Gaussian-prior hierarchical team effects with MAP/Laplace
parameter uncertainty, a regularized recency/strength feature model, a true
scikit-learn gradient-boosted tree model, and a calibrated ensemble. Models are
serialized into safe JSON numbers/tree arrays; untrusted pickle is never loaded.

Each annual holdout has four ordered roles: earlier training; trailing training
season hyperparameter selection; first half of the next season for Platt
calibration; second half for nonnegative ensemble weights; then untouched target
season. All matchup features use only outcomes eligible before the game date.
There are no market features in any independent model. Recent metrics shrink
against the actual available league population and historical team effects are
regularized. Recency half-lives and priors are declared modeling choices.

The committed real nflverse game-history benchmark contains816 annual holdout
games from2023–2025. Ensemble Brier≈0.22448 and log loss≈0.64032 beat the historical
home-win baseline but trail the indicative historical moneyline benchmark
(Brier≈0.21016). The ensemble does not automatically improve its best component.
No model is promoted to production. Historical quote timing and exact settlement
terms are unknown; those traditional moneylines are not DK Predictions contracts.
Calibration bucket counts partition the sample exactly, including0.5 and1.0.

```sh
python -m modeling.advanced /path/to/games.csv \
  --source 'Provider URL, retrieval and permitted use' \
  --as-of 2026-10-30T00:00:00Z --seasons 2023,2024,2025 \
  --out benchmark.json --model-out fitted-model.json
```

CLI artifacts are unsigned research files. The private service signs fitted
artifacts before accepting prediction requests. Production eligibility remains
false even after a simple-baseline research gate passes. Dataset revisions,
availability uncertainty, player/injury/weather effects and full ensemble
parameter uncertainty remain limitations. Week-block intervals, paired comparisons,
raw/calibrated metrics, diagnostic feature drift and model disagreement are saved.

## Private HTTP contracts

All POST endpoints require the existing server Bearer token. Neither this token
nor signing keys are sent to the frontend.

- `/models/benchmark`: `{csv,source,asOf,holdoutSeasons:[2023,2024,2025],firstSeason:2014}`
  returns `{report,model,summary,modelVersion}`. The returned model is signed.
- `/models/predict`: `{model,home,away,eventStart,restDifference?,division?}` returns
  model-specific and ensemble home-win YES estimates, conditional Bayesian
  parameter interval, disagreement and research-only status. Ties count as NO.
- `/trace`: `{model,home,away,eventStart,seed?,games:1..3,scenario?,postseason?}`
  returns representative generated games with shared play/player/source IDs.
  It deliberately does not present one game as an estimated probability.
- `/fit` adds `options:{recencyHalfLifeDays:180,conditionalShrinkage:true,
  strictAvailability:false}`. Conditional-pool prior strength is selected from
  chronological next-play-kind validation, rather than a guessed injury factor.
- `/simulate` adds `representativeGames:0..3` and optional
  `parameterUncertainty:{replicates:10..40,gamesPerReplicate:100..2000}`.

New signature version `numeric-canonical-v1` survives JSON number normalization
through browsers/Node (1.0→1, exponent notation and negative zero). Original
signatures remain accepted for legacy artifacts. Artifacts cannot be edited
without invalidating the signature.

## Sampling versus parameter uncertainty

The optional parameter calculation draws Bayesian-bootstrap weights at whole
historical-game level, retaining related plays under one block weight. Each draw
then simulates complete coherent games. At least8 historical game blocks are
required. The report separates the base-run Wilson interval, inner simulation
SE, a game-block parameter interval and noise-corrected parameter SD. The interval
includes finite inner-run numerical noise; structural and availability-cohort
uncertainty are not fully estimated. Increasing only the base count leaves the
separate bootstrap recipe and interval unchanged.

Strict fitting provenance requires `available_at`, `collected_at`,
`source_version` and `reliability=verified` on every row, all available by cutoff.
Unknown source availability is recorded as unknown; the adapter does not invent
publication timestamps. Historical game CSVs without availability metadata use a
clearly labeled conservative eligibility assumption and stay research-only.

Optional nflverse EPA/success/air-yard/YAC columns are retained for descriptive
research. Real observed target/carry shares, sack/turnover/explosive-play rates
and red-zone volume are summarized. Missing routes, snap shares and pressures
remain null. No unsupported weather or arbitrary player multipliers are silently
applied by the simulation service.

## Tests

Synthetic fixtures check mechanics, JSON tree parity with scikit-learn,
chronological feature eligibility, calibration boundaries, signed HTTP artifacts,
representative traces, availability gates and parameter-count invariance. They
are not NFL validation. The real benchmark report is separate from these tests.
