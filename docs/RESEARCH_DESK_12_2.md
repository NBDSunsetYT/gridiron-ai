# GRIDIRON AI 12.2 — football research desk

Public reference reviewed November 4, 2026: https://www.propsmadeeasy.com/how-it-works.
Its public page embeds its own public feature guide. Member-only tools were access-restricted and were not accessed. No subscription was purchased, private API used, proprietary implementation copied, or advertised accuracy independently verified.

The guide describes an optimizer, proprietary market-average pricing, line-movement signals, bookmaker selection and combination building. Its navigation also lists trends, simulation and touchdown tools. Its disclaimer at https://www.propsmadeeasy.com/copy-of-terms-conditions says projections do not guarantee accuracy. Market-price agreement, closing-line value and outcome hit probability are different measurements. None guarantees future profit.

## Implemented in the existing application

- NFL/CFB research board alongside the existing cards; player/team/market search; existing probability/value/difference sorting and exact matchup filtering.
- Selection following, keyed to sport, provider event, verified event crosswalk, kickoff, player ID, statistic, market, period, side, exact line and sportsbook. Quote changes and display-name changes do not erase follows. Signed-in preferences reuse the existing owner-scoped Supabase preference workflow and its retryable device mirror. No financial records move or change.
- Mean simulated statistic alongside the line for complete-game results. Historical distributions instead say **observed game average**, never a model projection. The statistic difference is not financial edge.
- Chronological observed-game charts with Last 5, Last 10 and explicitly partial season samples; actual denominators and equality counts. Histograms cannot establish chronology. Older snapshots without paired observations say so until the normal evidence refresh obtains them.
- Compact historical evidence adds at most 24 paired observations per statistic. It retains actual game IDs, season/week and publication-event dates where available, without inventing NFL dates or storing simulated plays.
- Same-selection sportsbook comparisons use only exact identities, thresholds, sides and periods among loaded pages. Current quotes expire after five minutes. Conflicting observations at the same book/time are flagged rather than ranked.
- Inspectable other-book reference: for each matched Over/Under pair, divide the selected side's implied probability by the sum of both sides; equal-weight at least two other books, excluding the selected sportsbook. Both observations must be within 60 seconds and current. Restricted to supported integer statistics at half-integer lines, avoiding a missing push probability. It is a market benchmark, not an independently validated probability or proprietary sharp average.
- Existing combination workflow remains accessible from each selection. Actual event-contract combination payouts still require verified platform rules. Nothing automatically records a wager.

## Preserved safeguards and costs

No simulation-count reduction, model-method change, new polling, paid resources, dependency additions, database migration, account change, financial mutation, research deletion, or provider-key change. Existing shared public caches and per-game background work remain. Searching, following, changing layouts and comparisons use already-loaded evidence, without starting new simulations or upstream provider requests.

Historical model data and sport-specific validation remain separate. Recalibration is shown only when its existing validation gate passes. Monte Carlo sampling precision remains separate from model uncertainty. Prices from PropLine are sportsbook reference observations; they do not become DraftKings Predictions event contracts.

Coverage is limited to available NFL/CFB feeds and loaded pages. No new baseball/NBA models, reliable future-price signal, proprietary sharp-book weights, guaranteed picks, complete market coverage, or verified net-value claim was added. Structural injury, weather, role and roster uncertainty remains visible wherever unsupported.

## Verification

Automated mechanics fixtures are labeled synthetic and are never production data. Numerical tests cover weighted distributions, chronological samples, exact matching, quote age/conflicts, opposing-side normalization, asynchronous quote rejection, target-book exclusion and stable selection preferences. Existing model, ledger, account isolation, combination, PWA and multi-tab request-deduplication checks are retained.

Live deployment and browser results are recorded separately in `docs/reports/research-desk-production.json` and `docs/reports/research-desk-release.json`. Mobile browser emulation is not a physical iPhone installation test.
