# Player-contract sources and operator integration

Normal app use does not require a dataset, credentials, or manual price entry. **Analyze All Player Props** discovers the authorized sources that are actually available and labels each venue independently.

## DraftKings Predictions

No authorized direct DraftKings Predictions event-contract feed is configured in this deployment. DraftKings Sportsbook odds and third-party sportsbook APIs are not treated as Predictions contracts. The app does not scrape private endpoints, bypass location controls, or silently substitute another exchange's settlement rules.

The server includes an explicit adapter contract for an operator's licensed source. This is an application integration schema, **not an official public DraftKings API**:

- `GRIDIRON_DK_PREDICTIONS_FEED_URL`: operator-controlled, public HTTPS endpoint. Use header credentials, not a token in the URL.
- `GRIDIRON_DK_PREDICTIONS_FEED_AUTHORIZED=1`: operator attestation that this exact event-contract feed is authorized. Its absence disables the request.
- `GRIDIRON_DK_PREDICTIONS_FEED_TOKEN`: optional private bearer credential, sent only to the configured endpoint. Redirects are rejected.

The response is `{schema: "gridiron-player-prop-contracts-v1", provider: "DraftKings Predictions", contracts: [...], nextCursor: null | string}`. At most 1,000 contracts per page and four pages are read. Additional pagination is reported as incomplete instead of claiming full coverage.

Each contract must satisfy `authorizedPropContractSchema` in [providers.ts](../lib/player-props/providers.ts): exact event/contract/game and GSIS player IDs, roster name/team, statistic, numeric threshold/operator, trusted kickoff, binary prices in cents, quote time, source/rules URLs, full rules, and an agreeing structured settlement definition. Optional fees must be explicit verified decimal cents with source and rounding terms; absent fees remain unavailable. The trusted NFL schedule and current roster independently check the mapping.

Quotes more than two minutes old are historical. Missing asks, suspended/closed status, unsupported rules, mismatched thresholds and conflicting player identities do not become current opportunities. Every quote remains a research observation; no order is placed and no fill is guaranteed.

## Separately labeled Kalshi alternative

Kalshi documents unauthenticated read-only market-data access. The implementation uses its fixed public `/events`, `/series/{ticker}` and `/structured_targets` endpoints. Nested market definitions are fetched in bounded pages of ten events and filtered against trusted upcoming games. This avoids hundreds of separate requests; the current `/markets` API supports only one `event_ticker` per request. Requests are paced, 429 responses receive bounded exponential backoff, pagination is bounded, duplicate work is cached for one minute, and an overall deadline prevents an expensive unbounded scan.

Supported discovery series are passing yards, passing touchdowns, passing attempts, completions, interceptions thrown, rushing yards, rushing attempts, receiving yards, receptions and touchdowns. Defensive interception, period, ladder, protected, head-to-head and season contracts have different rules and are not relabeled as these markets.

Structured player/team targets establish the provider identity. Their exact normalized name and NFL team must then match a unique current GSIS roster identity. Vendor `player_stats` projections and stale target roster status are deliberately not used as independent NFL model evidence. Unmatched identities stay unmapped; fuzzy name guesses are not accepted.

The original numeric floor strike and the equivalent integer `N+`/`gte` threshold are both retained. Both YES and NO bids/asks are recorded when present. Opposite-side displayed quantities are inferred only when the documented binary complementary prices reconcile exactly. `updated_time` is retained as market metadata, not misrepresented as the time a quote changed. Quote freshness uses the time the public BBO was observed and is rechecked when a saved result is read.

### Settlement coverage

The currently verified `FOOTBALLENTITYSTAT` terms document includes regulation plus overtime, subject to the individual market's period definition. Its participation and exceptional-event provisions are materially different from a simple universal binary payout. Active players who never participate and some interrupted/postponed games can settle at a discretionary fair price.

Consequently, compatible simulation probabilities describe **participation and normal game completion**. They are not unconditional probabilities of every possible contract settlement. Discretionary fair-price cases and unsupported availability mixtures withhold unconditional fair value and net EV.

The complete-game engine attributes offensive rushing/receiving touchdowns. A total-touchdown contract can also require defensive or return-touchdown coverage. Those contracts are discovered but marked unsupported for exact model valuation rather than silently evaluated using a narrower statistic.

### Fees

The actual official fee schedule retrieved for this release was effective July 7, 2026. It includes a multiplier-dependent taker formula and no settlement fee, but account/broker precision, fill-level rounding, per-order rebates and effective event overrides affect the entry cost. The old simple whole-cent ceiling is insufficient. Series metadata alone does not establish all of those terms. Public Kalshi entry fees and after-cost EV therefore remain unavailable instead of assuming zero fees or an obsolete formula.

## Optional manual fallback

`normalizeVerifiedManualProp` accepts a complete, user-verified structured snapshot after the private app endpoint authenticates its owner. It retains its original quote capture, exact rules and explicit costs. Manual snapshots are never called live or executable, even when recently entered. Recording research never records a wager automatically.

## Primary references

- [Kalshi public market-data quick start](https://docs.kalshi.com/getting_started/quick_start_market_data)
- [Current market filtering and single-event semantics](https://docs.kalshi.com/api-reference/market/get-markets)
- [Structured identities](https://docs.kalshi.com/getting_started/targets_and_milestones)
- [Full-game player-stat settlement terms](https://assets.kalshi.com/contract_terms/FOOTBALLENTITYSTAT.pdf)
- [Official fee schedule](https://kalshi.com/docs/kalshi-fee-schedule.pdf)
- [Current fee precision and rounding](https://docs.kalshi.com/getting_started/fee_rounding)
- [Event fee override history](https://docs.kalshi.com/api-reference/events/get-event-fee-changes)
- [Public API rate limits and backoff](https://docs.kalshi.com/getting_started/rate_limits)

The source verification report records what was observed at collection time. It is not a seeded price table, an execution promise, or a statistical calibration result.

## Executed source verification

The final read-only source check on October 30, 2026 selected 14 real upcoming games in the next seven days and verified 4,100 Kalshi contracts across 13 games with listed markets. All event pagination completed in 6.847 seconds. The normalizer marked 3,552 stat definitions compatible with conditional full-game evaluation, withheld 548 touchdown definitions from exact model valuation, and rejected 65 closed or inconsistent identity definitions. Current GSIS mapping and model evaluation are independent subsequent checks; these counts are not predictions or calibration results. See [the timestamped source report](reports/v6-market-source-verification.json).
