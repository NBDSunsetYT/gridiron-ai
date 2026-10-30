# GRIDIRON AI 2.0 upgrade audit

## Baseline inventory

The prior source already contained a Next.js frontend, user-scoped SQLite ledger, email/password sessions, manual market imports, optional authorized odds/OpenAI adapters, empirical observation tools, parlay independence/joint-observation comparison, PWA assets, and Docker instructions. The 1.0 source was not a licensed all-source NFL research system. It did not contain a trained opponent-adjusted player ensemble, production injury service, verified historical accuracy, or a deployed sportsbook execution system.

No pre-existing user database was found during the initial workspace inventory. The upgrade nevertheless supports an existing persistent database: migration001 remains immutable and additive migration files extend it. Do not replace a deployed DATA_DIR with an empty directory. Migration checksums, consistent snapshots before pending upgrades, ownership guards, append-only history, and recovery procedures are documented in [MIGRATIONS.md](MIGRATIONS.md).

## Implemented in 2.0

- Server-backed binary YES/NO contract entry with Decimal price/fee arithmetic, explicit settlement/equality rules, immutable quote/prediction/settlement snapshots, and a distinct paper portfolio.
- Python FastAPI service fits signed empirical model artifacts from supplied real play-by-play CSVs, runs 1,000–100,000 seeded simulations, and returns joint same-run outcomes. No trained artifact or historical dataset is silently substituted.
- Same-run joint parlay research with explicit independence comparison and verified combined sportsbook quotes for EV; multiplied standalone prices do not represent an executable same-game parlay price.
- Injury source/verification timestamps and freshness checks, explicit affected-entity links, replayable simulation input storage, durable invalidation/research jobs, Next after() dispatch, and operator-run recovery worker. Unsupported injury scenarios block rather than apply guessed multipliers.
- Persisted conversations, preferences/watchlists, simulation jobs, model registry/history, manual closing-price comparisons, and prospective score/calibration records.
- Automatic consistent pre-migration SQLite snapshots and explicit operator backups; encrypted account exports include research/preferences and exclude authentication secrets.
- A real public nflverse retrospective baseline audit, source citation/hash, chronological holdout and week bootstrap interval. This audit reports weak results honestly.

## Evidence boundary

The public-data audit contains 272 held-out 2024 games, a fixed45.5 total threshold and expanding fit initialized with2023. Brier≈0.25564 is worse than the constant50% benchmark0.25; log loss≈0.70457. The week-bootstrap95% Brier interval is approximately[0.24622,0.26372]. The baseline is not promoted. It uses no historical sportsbook quotes and therefore establishes neither market edge nor exchange profitability. It does not validate the separate play-by-play simulator. Retrospective results are kept apart from predictions actually captured before events.

## Still configuration-dependent or unavailable

OpenAI, The Odds API and the private Python service require server configuration. DraftKings Predictions has no direct licensed feed integration; binary prices are manually entered and verified. Injury updates are user/source supplied, not an independently licensed injury/news wire. Model/cohort uncertainty is not fully estimated. Simulator results do not imply current roster, weather, coaching, news or opponent-adjusted ensemble validity. Source attestations and settlements remain user-entered evidence, not independent verification.

Automatic injuries only affect explicitly declared references and supported evidence-backed scenarios. The worker blocks missing cohorts, unsupported joint scenarios and expired events; transient service failures retry within documented limits. Durable recovery needs an operator scheduler. Optional encrypted device snapshots provide read-only offline ledger history; offline writes, background push, biometrics, OCR and automated wagering are not delivered.

## Release verification

Use the final delivery test report for executed counts. Source review or an npm command in a guide is not evidence of a passing test. Docker configuration is supplied; no hosting URL, paid-feed entitlement, physical iPhone install, or production profitability is claimed without an actual check.
