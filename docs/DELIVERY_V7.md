# GRIDIRON AI 7.0 delivery and verification

**Live application:** https://gridiron-ai-gray.vercel.app  
**Source:** https://github.com/NBDSunsetYT/gridiron-ai  
**Database:** existing Supabase project `qdtdjbapdipopncklsdb`  
**Deployment:** `dpl_C1pqKr9AceYSeq19LL2XkNWZBp4f`, READY  
**Acceptance:** deployed with verified private-account and saved-research workflows. **Full automatic NFL scanner acceptance remains blocked by database capacity and missing authorized DraftKings contract access.** This is not a full-completion or profitability claim.

## Preserved application and security

This upgrades the existing application rather than replacing it. The Next.js frontend/API, private Python/FastAPI compute, Supabase authentication and PostgreSQL records, financial ledger, saved research, conversations and iPhone PWA remain preserved. The operational Python service runs privately in the existing **Vercel Services** project. Read-only inspection of the connected Render account found one workspace and **no services**; no Render backend URL is claimed and no paid service was created. The earlier free-service attempt returned HTTP402. Current billing readiness was not retested.

Nineteen managed database migrations match their actual native versions and SQL hashes. All **57 public tables have row-level security**. Existing user records were not reset, deleted or reassigned. Recovery protection includes the verified source Git bundle/archive and encrypted database checkpoints; it is not a claim of provider PITR coverage or complete managed Auth/Storage reconstruction. See [database preservation evidence](reports/v7-database-preservation.json) and [recovery procedures](DATABASE_RECOVERY_V7.md).

The daily application admission bound is **500,000 primary complete games**, retaining existing reservations. This does not purchase compute, change a hosting tier or override provider limits. Public research writes pause at a **450MB database reserve boundary** to protect personal-record storage within the current free 500MB database. Financial operations and existing saved research remain available.

## DraftKings Predictions is the primary market

The primary reference is [**DraftKings Predictions → Sports → NFL**](https://predictions.draftkings.com/en/markets/football/nfl), not DraftKings Sportsbook. Both **ANALYZE ALL NFL MARKETS** and **ANALYZE PLAYER PROPS** perform real backend requests. Without an authorized DraftKings feed they explicitly return unavailable, zero DraftKings contracts and no substitute research job. The preserved default player-prop API follows the same policy.

Public DraftKings HTML and its NFL navigation were inspected without private API calls or access-control bypasses. That HTML did not supply verified NFL contract IDs or executable matchup quotes. No authorized live DraftKings feed credentials are configured. A strict server-side adapter supports exact NFL event-contract definitions, percentage display, distinct bid/ask/last prices, fees, quote times and settlement conditions. An optional manually verified capture stays historical and private. American sportsbook odds are never silently substituted.

**Kalshi is an explicitly selected alternative.** Its actual source identity, rules and observed prices remain visible; equivalence to DraftKings is not claimed. This release's read-only discovery verified 5,217 alternative contracts across 14 games: 1,000 game markets and 4,217 player markets. Unsupported touchdown scopes and other incompatible definitions are withheld. Discovery is not evidence that the complete scan finished or that an observed quote guarantees a fill. See [actual market-source verification](reports/v7-market-source-verification.json).

The official [DraftKings fee disclosure](https://myaccount.draftkings.com/documents/fee-disclosure?product=predict) was independently verified. The public `/api/nfl/pricing` reference endpoint returned HTTP200 with verified semantic version `2eda9f727eb9e4647e36fba89159c31425198f719422e7d7feb647c6c32669b6`. Its calculator retains venue-specific fees, fractional cents and whole-transaction rounding. It is a **standard-cost estimate**, not a discovered quote, account invoice, actual fill or transaction record. Unknown venue, account terms or settlement exceptions withhold unsupported value. See [the access and fee audit](reports/v7-draftkings-access-audit.json).

## Implemented research and mobile behavior

Primary navigation is **Home | NFL | Props | AI | Wallet**. Existing advanced tools remain accessible. Public schedules and saved NFL research are available as a guest; GRIDIRON AI sign-in protects personal records and never requires a Supabase dashboard identity.

The unified NFL API evaluates exact full-game winner, spread, total and team-total contracts alongside supported player outcomes. Player IDs, teams, opponents, thresholds, Yes/No direction, overtime and settlement definitions are checked. Winner contracts with partial tie payments report tie probability and expected settlement separately; full-payout Yes/No probabilities are not mislabeled complements.

The existing 10,000/50,000/100,000 complete-game engine is preserved. Passing and receiving statistics emerge from shared plays; score, margin, total and player frequencies retain their correlations. Monte Carlo error is separate from parameter-bootstrap sensitivity. Unsupported numerical injury/weather assumptions are withheld instead of receiving arbitrary multipliers. Published injury/practice evidence is distinguished from confirmed inactives; complete official game-day inactive coverage and calibrated availability mixtures are unavailable.

Immutable prediction snapshots preserve captured prices, rules, assumptions, source times, model version and distributions. Ranking views use actual supported metrics. Calibrated probabilities remain unavailable without sufficient prospective evidence and an approved artifact. The four-game, 20-definition retrospective audit has Brier **0.2896930985** and log loss **0.8011373769664702**; it is explicitly **not promoted** and establishes neither prospective calibration nor market advantage. See [the historical audit](reports/v7-game-market-historical-audit.json).

The private joint-outcome lab preserves supported same-game player combinations; unsupported game-contract combinations are withheld. A simulated joint probability does not establish platform combinability or a traditional parlay payout. Actual combined execution payouts remain unavailable without verified platform rules.

Wallet records actual manually entered contract price, amount spent including fees, optional quantity, settlement payout and dates. Fractional-cent fee metadata is retained exactly while actual cash debits/credits use whole cents. Deposits, withdrawals, transfers and returned stakes are not counted as betting profit. Research never becomes an actual wager automatically.

## Actual production verification

The following ran against the actual HTTPS deployment, with no mocked production responses:

| Workflow | Executed result |
| --- | --- |
| Public saved-research API | **12 checks passed**, explicitly scoped to partial saved research; full scanner flag remains false. |
| Public Chromium | **14 checks passed**, desktop and iPhone-sized viewports, real saved research and offline shell. |
| Public WebKit | **14 checks passed**, desktop and iPhone-sized viewports, real saved research and offline shell. |
| Private Chromium | **6 checks passed** using isolated disposable accounts. |
| Private WebKit | **6 checks passed** using isolated disposable accounts. |
| Private session/persistence/account isolation | **6 checks passed** through ordinary authenticated HTTPS requests. |
| QA cleanup | **4 checks passed**; only the two exact server-marked disposable QA identities were removed. The original account remains. |

The **40 production browser checks** are the public 14+14 and private 6+6 above. They are not physical iPhone installation tests. Earlier failed GitHub-runner evidence remains retained: it found the real storage/read limitation and then a test-selector assumption about an already expanded card. The corrected ordinary HTTPS browser runs passed. Those earlier failures are not rewritten into successful full-scan results.

The isolated financial example verified starting $500 + deposit $100 − withdrawal $150 = $450; a $42 contract debit followed by a $100 actual settlement produced **$58 realized P/L and $508 available cash**. Transfers did not change the combined balance. A one-cent contract with 0.9-cent fee metadata and an actual refund also reconciled. Fresh sessions and production redeployments preserved the records. These were explicitly marked test records, not real bets, profits or the owner's balances; they were subsequently removed with the disposable identities.

Production reports:

- [Scoped public API](reports/v7-production-public-scoped-workflow.json)
- [Public Chromium](reports/v7-production-public-chromium-browser.json) and [public WebKit](reports/v7-production-public-webkit-browser.json)
- [Private Chromium](reports/v7-production-private-browser.json) and [private WebKit](reports/v7-production-private-webkit-browser.json)
- [Ordinary private persistence](reports/v7-production-persistence.json) and [QA cleanup](reports/v7-production-qa-cleanup.json)
- [Deployment/source correspondence](reports/v7-vercel-production-deployment.json)
- [Initial full-scan failure](reports/v7-production-public-github-initial-failure.json)

Local verification passed **506 TypeScript unit tests**, **103 Python tests** including all three complete-game modes, all **80 distinct desktop/iPhone-sized browser tests**, all **19 managed SQL migrations and compatibility checks**, TypeScript compilation and the production build. Two initial local browser artifact collisions were rerun in isolation and passed. Built public client assets passed an exact known-credential/QA-value byte scan: **94 assets, 2.42MB, zero matches**. Focused tests overlap these totals and are not added to inflate them.

Exact source-release commits must also pass the [Verify GRIDIRON AI workflow](https://github.com/NBDSunsetYT/gridiron-ai/actions/workflows/ci.yml) on a push event before tagged archive publication. Archives are checked for integrity, unsafe paths, private databases and configured credentials. Vercel's Git App is unconnected; this deployed through its authorized native source API, not a claimed automatic Git deployment.

## Capacity and remaining external requirements

**The full 14-game scanner did not pass.** The real explicit alternative run reached six completed games, with **5,400 immutable Yes/No outcome rows** including partial subsequent work. The database reached about **450.22MB**, triggering the reserved public-storage guard. About 236MB is live immutable prediction history and 109MB is live quote history. A safe one-time ordinary VACUUM/ANALYZE reclaimed only about 196KB; even a locking full rewrite could not provide sufficient ongoing capacity. No history was deleted, public guard waived, counter reset or paid plan enabled.

Saved rows remain inspectable and personal Wallet operations remain available. A newer empty failed run no longer erases the saved prior result set. Expensive unfiltered historical-model reads were removed, and capacity failures no longer start automatic retry jobs. Scheduled dispatch remains active every 15 minutes; its successful callback does **not** mean capacity-blocked research completed.

Finishing the complete ongoing research workflow requires additional persistent capacity or an approved durable archive architecture. The operator's current official [Supabase pricing](https://supabase.com/pricing) lists Pro **from $25/month**, including 8GB database capacity for the first project under its stated terms. No billing upgrade was initiated; account-owner authorization is required. The existing project and its records must be retained.

Other remaining requirements:

- Authorized DraftKings Predictions contract access is missing. Public Kalshi research and the official fee reference do not supply it.
- General OpenAI conversation requires the missing server-side credential. Source-cited evidence briefs and calculated private account reports work and are labeled nongenerative.
- New-account email confirmation still needs the operator to correct the existing Auth production return-URL allowlist/Site URL, which currently falls back to localhost. Existing confirmed-account sign-in works. Confirmation and RLS were not disabled. Apple sign-in remains disabled/hidden.
- Numerical weather shocks, calibrated injury-availability mixtures, unsupported settlement outcomes and exact replay of superseded upstream raw bytes are not claimed.
- Physical iPhone Safari/Home Screen installation was not performed. Native IPA/Xcode work remains postponed.

## Install and obtain source

Open **https://gridiron-ai-gray.vercel.app** in Safari, then **Share → Add to Home Screen → Add**. The standalone manifest, 192px/512px icons, Apple touch icon, safe areas and mobile navigation are verified. The service worker caches public assets and the offline shell, excluding private APIs and authenticated HTML.

The complete allowlisted source ZIP, SHA-256 and archive-verification manifest are published through the versioned [GitHub release](https://github.com/NBDSunsetYT/gridiron-ai/releases/tag/v7.0.0) only after its exact source passes CI. See [iPhone/File instructions](IPHONE.md), [operator configuration](ENV_V7.md), [recovery guide](DATABASE_RECOVERY_V7.md) and [README](../README.md). Downloading a ZIP to iPhone Files does not execute the hosted web, Python or database backend.
