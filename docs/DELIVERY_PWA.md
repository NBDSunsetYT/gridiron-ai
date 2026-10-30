# GRIDIRON AI iPhone PWA release

Date: 2026-10-30. The existing application was extended and tested. Native IPA/Xcode work is postponed; existing native source was preserved.

**The frontend is live at https://gridiron-ai-gray.vercel.app.** GitHub publication and public HTTPS health/manifest/icon checks are verified. The Python service is deployed privately in the same Vercel project. Production deep health verifies Python and Supabase connectivity; anonymous ledger requests return 401 and direct public Python routes return 404. Eleven signed-in production workflow checks and eight actual-production browser checks have passed; see the source-linked evidence below. Actual 10,000/50,000/100,000-complete-game research runs passed; deployment-continuity verification is recorded separately. Render rejected the requested free backend with HTTP 402 pending account payment verification at https://dashboard.render.com/billing; no service or charge was created. The private Vercel Python service keeps the existing engine operational while the Render requirement remains unresolved. Supabase project `qdtdjbapdipopncklsdb` remains the existing durable database. No database reset or duplicate project was created.

## Preserved functionality and earlier verification

| Area | Result | Verification boundary |
| --- | --- | --- |
| iPhone PWA | Standalone manifest; real 192/512 icons and 180 Apple icon; Apple compatibility metadata; safe areas; responsive navigation; installation/status card with the actual current URL | Desktop/iPhone Chromium checks; no physical iPhone or Safari Home Screen installation was performed |
| Offline shell | Public assets/offline interface cached; authenticated HTML and private/no-store API responses excluded; cache failures preserve successful online responses; clearing caches can prepare the shell again | Service-worker tests and browser offline workflows passed |
| Cloud persistence | Supabase Auth/PostgreSQL, 47/47 public tables with RLS, five existing safe migrations, owner-scoped financial/research/conversation storage | Actual authenticated remote operations; no database reset or migration of real records was attempted |
| Hosted storage protection | `GRIDIRON_CLOUD_ONLY=1` forces Supabase even with an old SQLite cookie; hosted SQLite selection returns 409 | Unit tests and actual production-container checks; original SQLite workspace remains preserved |
| Complete-game simulation | Fresh historical fit of 25,303 actual plays, 10,000 coherent games, shared passing/receiving statistics, saved result and attestation | Actual private Python service and live Supabase through a local production Node server; retrospective replay, not a current NFL forecast |
| Account synchronization | Fresh-client sign-in reopened financial records, predictions, conversations and simulation; actual Node restart retained the same records | Isolated disposable accounts; both removed through authenticated deletion after verification |
| Ledger and contracts | Deposits/withdrawals, stake/settlement accounting, $525 test balance and $75 realized P/L, separate paper portfolio, fee-aware binary contract import and prediction | Clearly labeled SYNTHETIC financial/contract fixtures; no real wagers or actual DraftKings prices were invented |
| Injury evidence | Uncertain versus confirmed designations remain distinct; unsupported availability assumptions return 422 instead of arbitrary adjustments; retry-safe queue tests retained | Manual evidence and supported historical cohorts only; no official live injury feed is connected |
| AI tools | Four additional tests use actual temporary ledger/conversation records, scoped tool execution, streaming and saved citations | OpenAI transport was explicitly stubbed; live assistant returns 503 because `OPENAI_API_KEY` is not configured |
| Deployment package | Retained Railway IaC/CLI authoring, allowlisted local source upload, server-only variables, health checks, dynamic ports, non-root web container, private dual-stack Python worker | Both actual Docker images built and ran; local container checks are not a public deployment |

## Earlier PWA verification

- 209 application TypeScript tests passed across 36 files (10.33 seconds).
- All 26 production-standalone browser tests passed across desktop and iPhone Chromium (37.4 seconds).
- Six focused PWA unit tests and eight focused browser checks passed, including cache-clear recovery.
- Five deployment Node tests and two Python deployment-runtime tests passed.
- Production Next.js build passed after the final PWA changes.
- Eleven live-cloud workflow checks passed, with live AI explicitly reported unavailable.
- Actual backend restart continuity passed for finances, conversations and the signed 10,000-game simulation.
- Both actual deployment Docker images built. Container readiness reached the real Supabase service and private Python worker; anonymous financial access returned 401 and ephemeral SQLite selection returned 409.
- All 24 original SQLite data tables remained unchanged against the consistent pre-release backup; integrity checks returned `ok`.

The prior 42 Python modeling tests and real 50,000/100,000-game audits remain in the retained 4.0 reports. During that earlier PWA verification, modeling code was unchanged and those suites were not rerun. The current cloud worker release was tested separately below. A 100,000-game run does not establish calibration or market advantage. The model remains research-only and trails the indicative historical market benchmark.

Machine-readable evidence: [PWA checks](reports/pwa-readiness.json), [live cloud workflow and restart](reports/pwa-local-cloud-workflow.json), [original data preservation](reports/pwa-data-preservation.json), [QA cleanup](reports/pwa-live-account-cleanup.json), and [actual Docker checks](../deployment/railway/container-verification.json). Test accounts used reserved `example.test` addresses; no confirmation emails were sent.

## Current engineering checks

After the cloud-job and transport changes, the local suites passed 259 TypeScript tests, 60 Python tests, nine Node workflow checks, 28 desktop/iPhone Chromium checks, and a production Next.js build. A separate four-check Vercel compatibility suite and type check passed after the provider required Node middleware. The initial GitHub CI found two mobile interactions blocked by a development error overlay; the missing SVG list key was repaired, and all 28 browser checks then passed without forcing interactions. GitHub CI passed on the production runtime source commit `56fa00ed196d1e9d178eb8e15811e6c90bc20d9b`: [run 41111516709](https://github.com/NBDSunsetYT/gridiron-ai/actions/runs/41111516709). Subsequent commits have their own workflow status; an in-progress run is not reported as a pass.

The production npm dependency audit reports zero findings after the bounded PostCSS patch. Three development-tool findings remain in Vitest and its test-only dependencies; they are excluded from production runtime dependencies. Real historical calibration still does not support a claim of market advantage. Live OpenAI generation, authorized live DraftKings contracts and official live injuries remain unavailable without their credentials/feed access.

## Actual production workflow

Production deployment `dpl_KngiqGqVpG6o1iyrZ5ZQyKF5CnBp` is READY at the stable URL above. Deep health reaches the existing Supabase project and the private Python service. The API rejects anonymous financial access with 401; direct public Python routes return 404. Server secrets remain encrypted provider configuration, and the original simulation signing token was retained.

The [production workflow](reports/pwa-production-workflow.json) passed eleven checks: actual Supabase login and owner isolation; exact ledger settlement arithmetic; a clearly SYNTHETIC verified manual binary contract and cash-separated paper position; uncertain/confirmed injury handling and withholding unsupported adjustments; saved conversations; actual public NFL schedule ingestion; historical model fitting; 10,000 complete games; and fresh-session reopening of saved balances, predictions, conversations and simulation results. The current production fixture used 1,527 actual historical plays from 22 games; it is retrospective research with unverified availability evidence, not a current injury-adjusted NFL forecast. No real market quote was invented.

The [production browser report](reports/production-browser-pwa.json) passed eight checks across desktop and iPhone 13 Chromium emulation. Both signed in to the real hosted app, reopened the saved finances and attested 10,000-game distributions in a fresh browser session, and verified the actual offline shell excludes private APIs and authenticated HTML. No physical iPhone/Safari installation was performed. Live AI correctly returned 503 without credentials; tool/database tests use an explicitly stubbed model transport and do not establish a live provider response.

The [simulation-mode report](reports/pwa-production-simulation-modes.json) confirms actual remote 50,000-game and 100,000-game runs, in addition to the prerequisite 10,000-game run. The observed remote elapsed times were 90.276 seconds and 166.211 seconds respectively. Fresh-session readback, cross-owner rejection, same-play player correlations, coherent scores/joint counts, representative replay, convergence and reproducibility passed; finances remained unchanged. The separate 1,000-game parameter bootstrap retained the same interval across sample counts. Structural uncertainty remains unestimated. More simulated games reduce Monte Carlo sampling error; they do not validate the model or verify missing injury evidence.

Original SQLite preservation is confirmed for all 24 tables against its consistent pre-release backup; both integrity checks returned `ok`. The pre-production [encrypted recovery checkpoint](reports/production-recovery-checkpoint.json) covers all 47 public Supabase tables in a read-only repeatable-read transaction and passed authenticated decryption/JSON equality. It excludes Auth, Storage, managed configuration and secrets, has no off-site replication, and is not a complete PostgreSQL backup or a tested restore. Provider backup/PITR retention remains unverified. Cloud records synchronize across devices; legacy SQLite records remain preserved and require the owned encrypted-import workflow to move into a cloud account.

## Required external configuration

1. The Vercel frontend is deployed; [VERCEL.md](VERCEL.md) records the private Python fallback and gateway constraints. Render requires its account owner to complete payment verification before another free-service attempt; [RENDER.md](RENDER.md) preserves the tested configuration. No paid plan, worker or cron service was started. The older Railway configuration is retained as an alternative, not the active hosting provider.
2. Set server-side Supabase URL/publishable key and preserve the existing simulation token on both services. Do not use a service-role key in the web application. The deployment wrapper pins Supabase storage and the real HTTPS origin.
3. Configure Supabase Auth Site URL and allowed email redirects for `https://gridiron-ai-gray.vercel.app`, preserving existing authorized redirects, then verify signup/confirmation using an authorized account. The connected database tooling does not expose an Auth-config mutation. Existing password login was tested; actual email delivery and production redirect behavior were not.
4. Add `OPENAI_API_KEY` through the host's server secrets for live conversation. Never paste it into public source or browser code. Licensed odds or official injury feeds require their own authorized access; manual/CSV/OCR entry remains supported.
5. The supplied [full URL workflow](PWA_WORKFLOW_VERIFICATION.md) accepts durable queued simulation receipts and verified compact saved-model references. Run it against the actual deployment, check production logs and HTTPS assets, then perform Safari Share → Add to Home Screen on the user's iPhone. GitHub CI runs automatically on pushes; provider deployment workflows are prepared but require the provider's separate Git authorization or configured GitHub secrets.

No signed IPA, App Store or TestFlight release is part of this update. Logical encrypted exports are tested; complete normalized typed-table reconstruction and provider backup/PITR retention retain the limitations documented in [SUPABASE.md](SUPABASE.md).

## Source delivery

The updated source archive is `artifacts/gridiron-ai-pwa-source.zip`, with a matching `.sha256` file. It excludes credentials, financial databases, runtime caches, deployment SDK dependencies and signing material. Saving the ZIP to iPhone Files stores source; it does not execute Next.js or Python. The installed PWA requires the real hosted HTTPS backend.
