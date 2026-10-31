# GRIDIRON AI 8.0 delivery

Release status: 8.0 is deployed at https://gridiron-ai-gray.vercel.app. **48 scoped actual-production checks passed:** 15 public API checks,18 desktop/iPhone-sized Chromium/WebKit browser checks and 15 PWA checks. A real hosted 10,000-game NCAA result reopened on fresh requests and browser reloads. Full platform acceptance remains partial: licensed feeds and shared database capacity are unavailable, and new 8.0 private financial writes and physical iPhone installation were not tested. Final tagged source releases require successful CI for the exact tag commit. Earlier [7.0 delivery](DELIVERY_V7.md) and [DraftKings diagnosis](DRAFTKINGS_ACCESS.md) remain retained.

## Implemented

The existing application now has a shared NFL / College Football selector across Home, Games, Props, AI and Wallet. Signed-in sport preferences sync through owned records; guest preferences are device convenience settings. NFL and college identifiers, results and historical snapshots remain distinct. Existing NFL simulation and fitting code is preserved.

College research uses published ESPN schedules and a documented SportsDataverse ESPN-derived play-by-play release. A separate college simulator produces complete regulation/overtime games with shared passing/receiving events and NCAA mechanics. It supports 10,000, 50,000 and 100,000 games with reproducible seeds, sampling error, separately reported parameter sensitivity, source timestamps and explicit coverage gaps. Independent player distributions are conditional historical baselines. No contract threshold, price, calibrated probability or expected value is invented when market coverage is absent.

Signed-in college simulation history, saved reports and conversations use authenticated, owner-scoped persistence. A guest simulation is temporary and may disappear with cache expiry or a backend restart; it is never labeled durable. New public ingestion stays subject to the existing financial-data reserve. The scheduler refreshes available schedules; it does not automatically simulate an unsupported whole slate.

Wallet adds explicit NFL, CFB and Unspecified wager metadata and filters. Historical untagged wagers remain Unspecified. Sport, market, sportsbook and settlement-date filters affect betting performance; they do not relabel deposits, withdrawals, transfers or whole-account cash as profit. Exact-cent postings and fractional-cent contract costs retain their existing accounting rules. Predictions never become actual wagers automatically.

The AI desk retrieves sport-scoped real records and source-based briefs. Without a configured language-model provider, briefs and exact account reports are labeled calculated evidence rather than generated AI. Current general OpenAI generation remains unavailable.

## Source and deployment boundaries

| Source or service | Verified state |
| --- | --- |
| Existing Vercel web/API and private Python service | READY; actual public API 15/15, browser 18/18 and PWA 15/15 passed |
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

The retained local actual 10,000-game college run used BYU at Utah with 943 historical supported plays across 14 selected-team games. It completed locally in 8.159 seconds with 250.21 MB maximum resident memory, plus separately reported bootstrap sensitivity. Every score/player histogram contained 10,000 outcomes and shared passing/receiving totals reconciled. This was a real historical-data calculation, not a hosted execution claim. See [the executed run](reports/v8-cfb-actual-10000-games.json).

The actual hosted worker separately completed 10,000 BYU-at-Utah games in 15.837 seconds from the same verified historical input version, with 41 player distributions. The home win estimate was 0.5298, with Monte Carlo 95% interval [0.5200,0.5396] and a separate underlying-model sensitivity interval [0.23,0.78]. These are uncalibrated conditional-baseline outputs, not a claim of forecast accuracy. Score/player counts and shared passing/receiving means reconciled. The guest result was explicitly temporary and not saved to private history. This first result was lost from a different server instance; the original calculation evidence is retained in [the initial production report](reports/v8-production-football-initial.json).

After the public-cache repair, Texas at Missouri completed another 10,000 complete games in 18.551 seconds with 39 player distributions. Missouri’s raw estimate was 0.5373, Monte Carlo 95% interval [0.5275,0.5471], and separate parameter sensitivity [0.38,0.70]. A fresh API request reopened the same original result ID without another simulation. Public cached results remain temporary and source-validated; signed-in private saves use owned database records. See [the repaired actual production workflow](reports/v8-production-football.json).

The four-game retrospective pilot has Brier 0.3913260825 and log loss 1.0894075175. It performed poorly and was **not promoted**. Retrospective source retrieval does not prove historical publication availability; this small pilot cannot establish calibration, market advantage or stable accuracy. Injury availability, current roster changes, weather, independent opponent/talent adjustments and some penalty/special-teams coverage remain incomplete. Increasing simulations does not remove those limitations. See [the retained audit](reports/v8-cfb-historical-audit.json).

## Executed checks

- Local full TypeScript suite: 602 unit tests across 77 files passed; nonincremental typecheck and the final production build passed.
- Python suite: 153 tests passed, including existing NFL tests, 28 college engine/preparation/service tests, 16 BALLDONTLIE tests and 6 CollegeFootballData tests.
- All five disposable PostgreSQL verification scripts passed, including college storage/quota/RLS and Wallet sport metadata, backup/restore and ownership checks.
- 110 distinct desktop/iPhone-sized browser checks passed across 44 new checks and 66 preserved regressions. The 12 financial checks are included in those 66 regressions. Local browser checks used synthetic transport, with no production financial writes or new users.
- Native migration preservation verified 73 public tables with RLS, 2 real users retained and 49 pre-existing private/Auth table families with unchanged counts and content hashes. Existing shared compute accounting was preserved; no reset occurred.
- Actual production public API: 15/15 checks passed, including the hosted 10,000-game computation, fresh-request original-ID reopen, real schedules, honest provider diagnostics, sourced nongenerative explanations and private-route identity protection.
- Fresh independent GitHub runner: 18/18 actual browser checks passed on desktop Chromium, iPhone-sized Chromium and iPhone-sized WebKit, including reloads, player-distribution controls, source-family separation and sign-in boundaries. PWA 15/15 checks passed for HTTPS, manifest/icons, real worker registration, private API exclusion and offline fallback. No extra simulation was started by that runner.
- The actual runtime source commit also passed 602 unit tests, 153 Python tests, all five PostgreSQL scripts, typecheck, production build and the full 146-browser CI suite. The 110 local browser checks above are a selected subset and are not added to 146.
- Initial runtime guest-cache failure, a workspace tunnel failure and a same-document-navigation harness failure are retained separately. The cache repair and corrected browser harness passed fresh production verification; no application result was fabricated.
- Final tagged release assets publish only after a successful push CI run for the exact tag SHA. These 48 public checks remain scoped and do not establish full provider/account/calibration acceptance. No production private financial write or physical iPhone installation was performed.

The production API report retains `fullAcceptancePassed:false`. No authenticated BALLDONTLIE or CollegeFootballData response, live DraftKings contract feed, new 8.0 private financial write, backend restart/private-save workflow, physical iPhone installation or OS standalone launch is claimed.

See [database preservation](reports/v8-supabase-preservation-verification.json), [college API checks](reports/v8-college-api-verification.json), [college SQL checks](reports/v8-college-postgres-verification.json), [Wallet checks](reports/v8-wallet-local-verification.json), [gateway access audit](reports/v8-deployment-access-inspection.json), [independent production verification](reports/v8-production-github-verification.json), [implementation CI](reports/v8-runtime-ci-verification.json), [production browser checks](reports/v8-production-browser.json), [production PWA checks](reports/v8-production-pwa-verification.json) and [provider documentation audit](reports/v8-balldontlie-nfl-docs-audit.json).

## Persistence and remaining operator requirements

The existing database measured 451.59 MB, above the fixed 450,000,000-byte public research reserve within its free quota. Saved history and private Wallet remain available. Additional public persisted research is blocked; no history was deleted and the guard was not waived. Increasing provider capacity requires owner authorization and a reviewed application guard update retaining financial headroom. A paid plan alone does not change the fixed guard.

Owner requirements are Render's billing authorization, secure Render-side provider credentials/entitlement, authorized DraftKings event-contract access, sufficient persistent research capacity and a corrected authentication confirmation return-URL allowlist. Existing confirmed-account sign-in works; Apple sign-in and live general language-model generation remain unconfigured. No sportsbook credentials are requested.

Open the hosted link in Safari and use Share → Add to Home Screen. The manifest, icons, safe areas and private-data-safe service worker are preserved. [iPhone instructions](IPHONE.md) also explain saving source to Files: a source ZIP does not run a backend on an iPhone. Native IPA work remains postponed.
