# GRIDIRON AI 2.0: capabilities and limits

Executed checks are in [DELIVERY_REPORT.md](DELIVERY_REPORT.md). No synthetic market, injury, bankroll, or forecasting records are seeded into production.

| Feature | Operational scope | Remaining boundary |
| --- | --- | --- |
| Personal accounts | Scrypt passwords, hashed sessions, HTTP-only cookies, origin checks, rate limits, owner-scoped reads/writes | No email delivery, passkeys, MFA or managed SSO |
| Durable database | SQLite WAL/FULL synchronous commits on a persistent volume; same account across devices and restarts | Single-instance hosting; no Postgres database-native RLS or stateless deployment |
| Financial ledger | Exact Decimal/integer cents, balanced postings, starting balances, deposits, withdrawals, transfers, adjustments, credits, wagers, settlements, voids, refunds and cash-outs | Personal records only; no sportsbook account synchronization or execution |
| Financial reporting | Separate books/combined portfolio, realized P/L versus contributions, pending exposure, ROI, charts, CSV, audit reversals and reconciliation | No automatic bank-statement matching; displayed cash balance includes pending stake, available balance excludes it |
| Backups/migrations | Consistent snapshots before pending migrations, checksum history, encrypted account exports, recovery utility | Operator must provision encrypted off-site retention; no whole-account restore UI |
| DraftKings Predictions | Exact manual binary IDs, thresholds, asks/bids, liquidity, fees, settlement text, structured simulator rules, immutable quotes/forecasts | No authorized direct exchange feed or verified executable liquidity; citations remain user-attested |
| Generated contract valuation | Completed simulation probabilities; exact market/player/team/stat/threshold/equality matching; Decimal fee-aware value and stale flags | Legacy unstructured contracts need a new structured snapshot; prose rules are not automatically verified |
| Sportsbook markets | Manual/CSV American-odds imports plus server-side The Odds API adapter | Credential/entitlement dependent; Hard Rock coverage is not assumed; separate from Predictions contracts |
| Game simulation | Conditional empirical play-by-play bootstrap, shared QB/receiver events, possessions, downs, turnovers, scoring, clock, overtime, seeded 10k/50k/100k/custom games | Unvalidated baseline; penalties, full timeout strategy, future rosters, weather fitting and total model uncertainty remain incomplete |
| Historical NFL data | Local-file nflverse CSV/GZ normalizer, hashes, chronological fit and actual holdout reports | Not a continuously synchronized comprehensive warehouse; raw historical data is not redistributed |
| Injury intelligence | Append-only official/licensed citations, publication/check times, freshness, empirical cohort weights, confirmed-out distinction | User verification; no independently fetched official wire or guessed availability probabilities |
| Injury propagation | Referenced forecast invalidation, persisted replay inputs, supported scenario reruns, joint weighted outcomes and appended versions | Requires historical scenario labels; unsupported multi-player interactions block; recovery cron must be operated |
| Prediction audit | Prospective/retrospective separation, immutable settlements, Brier/log loss/calibration and price comparisons | No validated promotion or market superiority; sparse samples remain explicit |
| Real historical validation | 272-game league-total baseline plus four-game play-by-play holdout | Baseline underperformed 50%; simulator sample is too small; neither model promoted |
| Parlays | Aligned historical and same-simulation joint outcomes, separate independence estimate, verified combined offer EV | Push/repricing rules must be supported; no assumed multiplied executable quote |
| AI research desk | Real OpenAI tool calls, streaming, persistent conversations, scoped ledger/contract/injury/simulation context | Requires key; live calls unverified; no web/news search, autonomous simulation tool or independent specialist agents |
| Saved records | Conversations, preferences/watchlists, research, forecasts, simulations, notifications and paper positions in database | No external vector-memory synchronization |
| Paper portfolio | Hypothetical positions isolated from real cash | Snapshot prices are not actual fills |
| Mobile/PWA | Responsive terminal, mobile navigation, manifest/icons, offline public interface, reduced-motion support | Chromium iPhone emulation tested; physical Safari installation unverified |
| Encrypted offline history | Optional passphrase-protected, read-only device snapshot, saved timestamp, private APIs never cached | Device-specific, manually refreshed; no offline writes/sync |
| Alerts | Persistent in-app injury/rerun notices and source errors | No Web Push or automatic official-news collection |
| Advanced models | Empirical baseline and play-by-play engine | Bayesian hierarchical, boosted, weather-adjusted and calibrated ensembles not implemented/validated |
| Images/OCR | Original football diagram and manual/CSV import | Licensed logos/headshots, screenshot OCR and App Store binaries not bundled |

The app does not place wagers, request sportsbook passwords, bypass geolocation, or describe outcomes as guaranteed.
