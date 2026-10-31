# DraftKings Predictions source diagnosis — 7.0.1

Application: https://gridiron-ai-gray.vercel.app  
Requested market: **DraftKings Predictions → Sports → NFL**, https://predictions.draftkings.com/en/markets/football/nfl

## Actual production cause

The deployed adapter has **no configured authorized contract feed**. Read-only Vercel environment metadata shows that `GRIDIRON_DK_PREDICTIONS_FEED_URL`, `GRIDIRON_DK_PREDICTIONS_FEED_AUTHORIZED` and `GRIDIRON_DK_PREDICTIONS_FEED_TOKEN` are absent. There are also no OpticOdds, Betstamp or other odds-vendor credential names. No secret values were read or published.

The adapter's configuration guard returns before a provider HTTP request. The observed failure therefore does not establish a provider outage, HTTP429 rate limit, rejected player mapping, or an empty NFL inventory. The previous generic unavailable state hid this distinction. Both the NFL and preserved Props endpoints now return a structured diagnostic with a safe reason, stage, check time, retry policy and corrective action.

The connected Render account currently contains one accessible workspace and **no services**. There are no Render backend logs to inspect. The operational Python service is privately bound to the existing Vercel Services application. Its simulation engine and existing database records are unchanged by this repair. Actual production API/log/environment observations are retained in [the deployment inspection](reports/draftkings-production-inspection.json).

## Live access verification

**Exact live DraftKings NFL contracts verified accessible: zero.** This means no authorized accessible response supplied a complete current DraftKings contract/quote/settlement mapping. It does not mean that DraftKings has no NFL markets.

The public NFL page returned HTTP200. Offline inspection of the loader data in that public HTML confirmed NFL navigation, including game lines and player props. Embedded CMS event/selection identifiers were not complete live contracts: there were no verified price, bid/ask, quote-time and settlement records to pair with them. Translation strings such as “no markets” were not treated as an inventory result. Restricted application resource routes were not requested.

| Source | Verified evidence | Remaining access or definition gap |
| --- | --- | --- |
| [OpticOdds](https://developer.opticodds.com/docs/opticodds-for-prediction-market-makers) | Official documentation separately lists `draftkings_predictions`; documents native-source IDs, order books and probability-format quotes. Documented catalogue and NFL discovery requests returned **HTTP401: API key required**. | No entitled key or actual DraftKings quote sample was available. Exact DK identifiers, fees, thresholds and settlement rules still require verification. Defaults can be fee-adjusted, so normalized vendor prices cannot be called raw executable DK quotes. |
| [Betstamp](https://www.betstamp.com/odds/draftkings-predictions) | Explicit DraftKings Predictions/NFL support is advertised. Its documented endpoint returned **HTTP401 `missing_api_key`**. | Public normalized-odds examples do not verify native contract IDs, executable Yes/No prices, transaction costs or settlement terms. |
| [MetaBet](https://www.metabet.io/products/odds-api) | Public product documentation distinguishes `DRAFTKINGS_PREDICTIONS` from `DRAFTKINGS`. | A documentation example is not a tested live feed and lacks the complete exact-contract evidence required here. |
| [CDNA official data](https://data.crypto.com/docs) | A documented NFL read endpoint returned HTTP200. | Its exchange symbols/prices have not been matched to exact DraftKings retail contracts. Applicable licensing restricts AI processing/redistribution without suitable permission. No exchange payload was integrated or redistributed. |
| [DKeX](https://www.railbirdexchange.com/contact) | Official onboarding and connectivity contacts are public. | No authorized live session, entitled feed or verified retail-contract mapping is configured. |

Full request metadata, source citations, licensing qualifications and accessible fields are in [the dated source investigation](reports/draftkings-authorized-source-audit.json). No vendor was contacted, subscribed to or paid. Kalshi and traditional sportsbook lines are not replacements for the requested source.

## Error-state contract

The `providers[]` response retains its existing fields and optionally includes `diagnostic`. A diagnostic contains a finite `code`, stage, safe message/action, check timestamp, retry policy, operator requirement and observed HTTP status where available. It never includes a server token, configured endpoint query string, upstream response body or guessed account restriction.

- Missing feed URL, missing authorization attestation and invalid source configuration stop before HTTP or research writes.
- Missing credentials require evidence from an actual authentication rejection. A token is optional for sources that do not require one.
- HTTP401, HTTP403, HTTP404, HTTP429, server errors, timeouts and network failures remain distinct.
- A complete valid feed with no contracts can report no NFL markets supplied by that feed. An unreachable source cannot.
- Unsupported feed formats, incomplete pagination, incompatible definitions, failed identity mapping, unavailable quotes and stale prices are distinguished from empty inventory.
- A quote being readable does not establish model support, verified execution, after-fee value or calibration.

## Connecting an entitled source

An operator must first obtain licensed access that permits the intended research and display. The exact source must supply native contract/event identity, scheduled NFL matchup, player/team identity, threshold and comparison, Yes/No direction, current displayed price, available executable BBO, source clock, fees and full settlement conditions. Test actual responses before enabling consumer availability.

The existing operator adapter accepts the documented `gridiron-nfl-event-contracts-v1` envelope; the earlier player-only envelope remains supported. This is the application's integration schema, **not an official DraftKings API**. A raw vendor endpoint cannot be pasted into the feed setting unless its response has been correctly adapted and all required settlement mappings verified. A vendor catalogue entry is not enough.

Keep the source URL, optional bearer credential and `GRIDIRON_DK_PREDICTIONS_FEED_AUTHORIZED=1` in encrypted **server-only** deployment settings. The attestation records the operator's authorization; it does not purchase or create a licence. Do not use a `NEXT_PUBLIC_` secret, query-string API key, sportsbook password or browser session to bypass access restrictions. Existing Vercel/Supabase resources should be reused.

## Optional manual fallback

Signed-in users can open **Advanced Mode → Contracts → Import verified quote**. Record the exact event contract, source time, Yes/No price, transaction costs and settlement rules from an authorized observation. CSV/screenshot imports require review and confirmation. These observations remain private and labeled as manual; they do not become a live feed or an actual wager. Wallet records require a separate explicit financial entry.

## Verification scope

The repair adds diagnostic and UI tests around the preserved adapter. Synthetic responses are used only in automated tests to verify failure handling; they are never published as live data. Production verification must confirm the actual configuration diagnostic, guest NFL access, private endpoint authorization, UI layout and unchanged deployment resources. A simulated successful vendor response does not count as a verified live DraftKings feed.
