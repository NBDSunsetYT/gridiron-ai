# GRIDIRON AI 5.0 production verification

**Live application:** https://gridiron-ai-gray.vercel.app  
**Source:** https://github.com/NBDSunsetYT/gridiron-ai  
**Verified:** 2026-10-30, against the existing production application and database.

The application is deployed and its guest research, automatic 10,000-complete-game analysis, private Wallet and persistent conversation workflows passed production acceptance. This upgrades the existing application; it does not replace its database or require an end user to open a Supabase dashboard.

## Deployment and preservation

The production Vercel deployment is `dpl_4PakhDosuivMZSAj3DHFZBVhNceC`. It contains the Next.js web/API service and a private Python 3.12/FastAPI compute service. The stable HTTPS alias was assigned successfully. The deployment used an authorized source snapshot with 158 runtime files and SHA-256 manifest `34fe47e3674853b7c8294372520263dc25ada4422caa9f266c1a69b8a2303a22`; its metadata records the preceding Git base plus uncommitted release changes, rather than claiming those changes were already in that older commit. See [deployment evidence](reports/v5-deployment.json).

The database remains the existing Supabase project `qdtdjbapdipopncklsdb`. Additive migrations create three shared NFL tables alongside the 47 existing private tables. All 50 public-schema tables retain row-level security. Public NFL results and generic evidence briefs are separate from private finances, saved research and conversations. Shared mutations require a narrow server-only capability; guests cannot write directly to those tables or read protected model artifacts. Personal APIs continue to verify identity and enforce ownership.

A verified pre-upgrade Git bundle, consistent original SQLite backup and encrypted pre-change public-table checkpoint were retained. The checkpoint is not a full Auth/Storage or provider PITR backup. Existing user records were not reset or reassigned. Temporary production financial tests used only explicitly marked disposable QA identities and synthetic transactions, not the owner's account. Cleanup passed six additional checks: both exact QA identities and their owned fixture rows were removed through the session-revoking account-deletion flow, the pre-existing account count remained unchanged, and the private test question was absent from shared public tables. See [cleanup and isolation evidence](reports/v5-production-qa-cleanup.json).

Render previously rejected free-service creation with HTTP402 billing verification. No paid service was started. The operational Python service runs privately in the existing Vercel Services deployment; no public Render backend URL is claimed. Vercel's own Git App is not connected, so this release used its authorized native source-deployment API. GitHub source publishing and the existing verification workflow are separate from automatic Vercel Git deployments.

## Operational consumer workflow

The primary navigation is **Home | Games | Simulations | AI | Wallet**. A fresh guest immediately sees published NFL games. Game cards open current public research; selecting a game automatically retrieves a fresh saved result or queues backend analysis. **Analyze Game** performs the same complete operation without asking the person to upload statistics or configure a provider. Advanced controls and optional imports remain available behind Advanced Mode.

The production guest acceptance test selected the real upcoming Baltimore–Buffalo game `2026_08_BAL_BUF`. It observed a new job running and completing between 20:18:08 and 20:18:41 UTC. The result contains 10,000 coherent complete games, 26 published player distributions, two explicitly withheld player distributions, one representative game and 13 research citations. It is a new production computation, not a seeded result or an older cached identifier. Repeating the action returned the same fresh persisted result. See [guest workflow](reports/v5-production-public-workflow.json).

Statistics emerge from shared simulated plays: quarterback completions and receiver receptions, passing and receiving yards, scoring and player opportunities remain connected. Separate bootstrap runs estimate parameter sensitivity; increasing the main game count does not erase uncertainty in the underlying model.

Signed-in users automatically retain their owned saved analyses and conversation history. The production private checks recorded isolated synthetic deposits, withdrawals, a wager and settlement, then verified exact cash and P/L, preferences, saved simulation and private messages in new authenticated sessions. Guests and a different identity could not retrieve those records. Deposits are not profit, withdrawals are not losses, and transfers and returned stakes are not counted twice.

## Connected public sources and updates

Automatic research uses published nflverse-compatible schedules, play-by-play, injury/practice reports, snap counts, rosters, depth charts and weekly player/team statistics. Venue identity and available forecasts use public ESPN event information and Open-Meteo with validation. Provenance, collection times, available timestamps, missing coverage and source versions are retained. Changes in any of the seven quantitative source assets affect the input fingerprint; a checked timestamp alone does not cause needless simulations.

A supported existing Supabase Cron/HTTP schedule is active every 15 minutes. An actual scheduled invocation at 20:19 UTC produced a verified HTTP202, completed the public refresh, reused a fresh analysis and queued a changed/new game. Requests use short-lived, one-use HMAC signatures; no durable bearer token is placed in the managed HTTP queue. The refresh bounds work and daily compute, preserves snapshots and does not repeatedly simulate unchanged inputs. See [scheduled execution](reports/v5-background-refresh.json).

Verified public Kalshi NFL winner quotes are available as a separately labeled alternative. The app does not claim they are equivalent DraftKings contracts. Their actual threshold/outcome/rules, bid/ask and quote time remain visible. Missing fee information withholds fee-dependent expected value. No live DraftKings Predictions or Hard Rock feed is authorized in this environment; their prices are not invented. Verified manual, CSV and screenshot/OCR workflows remain optional advanced fallbacks.

## Executed checks

| Scope | Result |
| --- | --- |
| Final TypeScript unit tests | 324 passed |
| Final Python quantitative/service tests | 74 passed |
| Typecheck and production build | Passed locally and deployment build succeeded |
| PostgreSQL migration and security verification | All 10 migrations compiled; ledger/import preservation, RLS, capability denial, idempotency, lease fencing, immutable snapshots and compute limits passed |
| Local public full-stack workflow | 7 passed using actual source data and 10,000 games |
| Local browser acceptance | 36 passed, including desktop/iPhone-sized consumer flows and history escaping |
| Production guest API | 7 passed |
| Production public Chromium + WebKit | 20 passed across desktop and iPhone-sized profiles |
| Production isolated private API | 10 passed |
| Production private Chromium + WebKit | 8 passed across fresh authenticated sessions |
| QA cleanup and public/private SQL audit | 6 passed; only the two exact disposable test identities and their fixture rows removed |
| Actual scheduled refresh | Passed; restored to active 15-minute schedule |
| Production dependency audit | Zero runtime findings with `npm audit --omit=dev` |
| Deployment error/fatal log scan | No records in the initial post-acceptance scan |

The production total is **45 acceptance checks plus six cleanup/isolation checks**, not a claim of physical device installation. Reports: [local final checks](reports/v5-final-local-checks.json), [public Chromium](reports/v5-production-browser.json), [public WebKit](reports/v5-production-webkit-browser.json), [private API](reports/v5-production-private-workflow.json), [private Chromium](reports/v5-production-private-browser.json), [private WebKit](reports/v5-production-private-webkit-browser.json).

## Partial or unavailable capabilities

- **Injury-adjusted research:** current reports, practice participation and verified status changes are ingested. Questionable availability is not treated as certain. Statistically unsupported active/limited/inactive probabilities or lineup effects are withheld rather than supplied as arbitrary multipliers. Complete official inactive, route-participation, defensive-personnel and weather-adjustment coverage is not established by the available public sources. Automatic team win estimates remain an incompletely injury-adjusted historical baseline; numerical weather effects and calibrated active/limited/inactive mixture weights are not applied.
- **Model validation:** the complete-game engine is research-only. Its new automatic current-season pipeline has not established out-of-sample calibration or market advantage. The separate retained 816-outcome ensemble audit is labeled as a different historical benchmark; it does not validate these automatic play-by-play forecasts. Earlier 50,000/100,000-engine checks remain preserved, but this release's live automatic acceptance uses the default 10,000 mode.
- **AI generation:** source-cited evidence briefs work and are explicitly identified. `OPENAI_API_KEY` is absent, so live OpenAI specialist chat/tool generation is not claimed. Existing private AI tools remain implemented for operator configuration; no fabricated model output stands in for a provider response.
- **New-account email confirmation:** confirmed-account password sign-in works and was tested. The provider's current allowed-return settings reject the production origin and fall back to localhost. This requires an authorized operator Auth configuration change; the connected tools do not expose that mutation. The app does not bypass the allowlist or disable confirmation. See [account audit](AUTH_V5.md).
- **Apple sign-in:** the actual provider is disabled. The app hides the unavailable option; no real Apple consent flow was tested.
- **Exact raw-source replay:** shared automatic snapshots persist results, summaries and source versions/hashes. Raw public play-by-play and fitted temporary artifacts remain worker-cache files; exact replay of superseded mutable upstream bytes is not guaranteed. The preserved private fitting workflow retains its existing complete artifact storage.
- **Recovery:** complete encrypted account exports are tested, including streamed large responses. Large one-shot restore remains subject to the host's 4.5MB request limit; full normalized warehouse/Auth/Storage reconstruction and provider PITR retention are not verified. Preserved legacy SQLite data is not silently assigned to a cloud user.
- **Test tooling:** full dependency audit still reports three development-only Vitest/mocker/tinypool findings. No runtime dependency findings were reported. A reviewed test-tool upgrade remains separate from this frozen production release.
- **Physical iPhone installation and native IPA:** Chromium/WebKit iPhone-sized checks passed; an actual Safari Home Screen installation was not physically performed. Native IPA/Xcode work remains postponed.

## Open and install

Open **https://gridiron-ai-gray.vercel.app** in Safari on iPhone. Browse as a guest, tap a game, and let the backend retrieve or calculate research. Choose **Share → Add to Home Screen → Add** to install. The manifest, 192px/512px icons, Apple touch icon, standalone display, safe areas, responsive navigation and public-asset offline shell are implemented. Private APIs and authenticated HTML are excluded from service-worker caches.

Sign into GRIDIRON AI when using personal records. Users do not need a Supabase dashboard account. Source ZIPs are for development and recovery; downloading them to iPhone Files does not execute the Next.js or Python backend. See [iPhone guide](IPHONE.md), [operator environment configuration](ENV_V5.md) and [developer launch commands](../README.md).
