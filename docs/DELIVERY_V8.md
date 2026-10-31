# GRIDIRON AI 8.0 delivery

Release status: implementation and local checks complete; final hosted 8.0 acceptance is pending. The existing app remains at https://gridiron-ai-gray.vercel.app. This report will distinguish the final deployed checks from local evidence when production verification finishes. Earlier [7.0 delivery](DELIVERY_V7.md) and [DraftKings diagnosis](DRAFTKINGS_ACCESS.md) remain retained.

## Implemented

The existing application now has a shared NFL / College Football selector across Home, Games, Props, AI and Wallet. Signed-in sport preferences sync through owned records; guest preferences are device convenience settings. NFL and college identifiers, results and historical snapshots remain distinct. Existing NFL simulation and fitting code is preserved.

College research uses published ESPN schedules and a documented SportsDataverse ESPN-derived play-by-play release. A separate college simulator produces complete regulation/overtime games with shared passing/receiving events and NCAA mechanics. It supports 10,000, 50,000 and 100,000 games with reproducible seeds, sampling error, separately reported parameter sensitivity, source timestamps and explicit coverage gaps. Independent player distributions are conditional historical baselines. No contract threshold, price, calibrated probability or expected value is invented when market coverage is absent.

Signed-in college simulation history, saved reports and conversations use authenticated, owner-scoped persistence. A guest simulation is temporary and may disappear with cache expiry or a backend restart; it is never labeled durable. New public ingestion stays subject to the existing financial-data reserve. The scheduler refreshes available schedules; it does not automatically simulate an unsupported whole slate.

Wallet adds explicit NFL, CFB and Unspecified wager metadata and filters. Historical untagged wagers remain Unspecified. Sport, market, sportsbook and settlement-date filters affect betting performance; they do not relabel deposits, withdrawals, transfers or whole-account cash as profit. Exact-cent postings and fractional-cent contract costs retain their existing accounting rules. Predictions never become actual wagers automatically.

The AI desk retrieves sport-scoped real records and source-based briefs. Without a configured language-model provider, briefs and exact account reports are labeled calculated evidence rather than generated AI. Current general OpenAI generation remains unavailable.

## Source and deployment boundaries

| Source or service | Verified state |
| --- | --- |
| Existing Vercel web/API and private Python service | Preserved; final 8.0 production acceptance pending |
| Existing Supabase `qdtdjbapdipopncklsdb` | 20 additive migrations aligned; existing records retained |
| NFL public research | Published nflverse-compatible records, ESPN metadata and available weather references; missing inputs remain explicit |
| College public research | Actual published ESPN schedules and SportsDataverse play-by-play, with publisher/source provenance |
| DraftKings Predictions | Authorized event-contract feed absent; exact configuration/HTTP/mapping diagnostics, no sportsbook substitution |
| BALLDONTLIE NFL | Tested Render-only adapter; zero authenticated production endpoints verified, actual account tier unknown |
| CollegeFootballData | Optional Render-only adapter; no credential available, no authenticated production endpoint verified |
| Render data gateway | Tested isolated source published; one explicit free creation returned HTTP402 requiring owner payment-information authorization; no service or URL created |

BALLDONTLIE's documented Free/ALL-STAR/GOAT resource tiers describe provider requirements, not the owner's subscription. A successful Free teams probe would not establish odds/props entitlement. No purchase or trial was activated. Its DraftKings vendor denotes sportsbook reference prices; those prices do not become DraftKings Predictions event contracts or executable bid/ask quotes. The adapter withholds unsupported prices, identity mappings, fees and settlement equivalence.

The Render gateway has only FastAPI/uvicorn dependencies and bounded caches. Provider keys are read only after Render runtime and server-to-server authorization checks. `BALLDONTLIE_API_KEY` and optional `CFBD_API_KEY` belong only in Render Environment. Vercel receives only a verified gateway URL and a separate bridge token. No provider key has been copied there. The existing private Vercel quantitative service remains in place.

The default [Render Blueprint](../render.yaml) describes only this explicit-free gateway; the previous quant Blueprint is preserved at [legacy-quant.render.yaml](../deployment/render/legacy-quant.render.yaml). It has not been applied. Render Free has cold starts and allowance limits. The current HTTP 402 is a platform authorization requirement, not approval to choose a paid plan. The account owner must resolve it at https://dashboard.render.com/billing before a service can be created; provider secrets can then be entered securely in that Render service. No end-user dashboard or technical setup is required for available public research.

## Statistical evidence and limits

The retained actual 10,000-game college run used BYU at Utah with 943 historical supported plays across 14 selected-team games. It completed locally in 8.159 seconds with 250.21 MB maximum resident memory, plus separately reported bootstrap sensitivity. Every score/player histogram contained 10,000 outcomes and shared passing/receiving totals reconciled. This was a real historical-data calculation, not a hosted execution claim. See [the executed run](reports/v8-cfb-actual-10000-games.json).

The four-game retrospective pilot has Brier 0.3913260825 and log loss 1.0894075175. It performed poorly and was **not promoted**. Retrospective source retrieval does not prove historical publication availability; this small pilot cannot establish calibration, market advantage or stable accuracy. Injury availability, current roster changes, weather, independent opponent/talent adjustments and some penalty/special-teams coverage remain incomplete. Increasing simulations does not remove those limitations. See [the retained audit](reports/v8-cfb-historical-audit.json).

## Executed checks

- Local full TypeScript suite: 596 unit tests across 75 files passed; nonincremental typecheck and the final production build passed.
- Python suite: 153 tests passed, including existing NFL tests, 28 college engine/preparation/service tests, 16 BALLDONTLIE tests and 6 CollegeFootballData tests.
- All five disposable PostgreSQL verification scripts passed, including college storage/quota/RLS and Wallet sport metadata, backup/restore and ownership checks.
- 110 distinct desktop/iPhone-sized browser checks passed across 44 new checks and 66 preserved regressions. The 12 financial checks are included in those 66 regressions. Local browser checks used synthetic transport, with no production financial writes or new users.
- Native migration preservation verified 73 public tables with RLS, 2 real users retained and 49 pre-existing private/Auth rows unchanged by content hash. Existing shared compute accounting was preserved; no reset occurred.
- Final production 8.0 API/browser, live 10,000-game hosted execution, deployment logs and release-source CI are pending; they must not be inferred from local passes. Physical iPhone installation has not been tested.

See [database preservation](reports/v8-supabase-preservation-verification.json), [college API checks](reports/v8-college-api-verification.json), [college SQL checks](reports/v8-college-postgres-verification.json), [Wallet checks](reports/v8-wallet-local-verification.json), [gateway access audit](reports/v8-deployment-access-inspection.json) and [provider documentation audit](reports/v8-balldontlie-nfl-docs-audit.json).

## Persistence and remaining operator requirements

The existing database measured 451.59 MB, above the fixed450,000,000-byte public research reserve within its free quota. Saved history and private Wallet remain available. Additional public persisted research is blocked; no history was deleted and the guard was not waived. Increasing provider capacity requires owner authorization and a reviewed application guard update retaining financial headroom. A paid plan alone does not change the fixed guard.

Owner requirements are Render's billing authorization, secure Render-side provider credentials/entitlement, authorized DraftKings event-contract access, sufficient persistent research capacity and a corrected authentication confirmation return-URL allowlist. Existing confirmed-account sign-in works; Apple sign-in and live general language-model generation remain unconfigured. No sportsbook credentials are requested.

Open the hosted link in Safari and use Share → Add to Home Screen. The manifest, icons, safe areas and private-data-safe service worker are preserved. [iPhone instructions](IPHONE.md) also explain saving source to Files: a source ZIP does not run a backend on an iPhone. Native IPA work remains postponed.
