# GRIDIRON AI iPhone PWA release

Date: 2026-10-30. The existing application was extended and tested. Native IPA/Xcode work is postponed; existing native source was preserved.

**Public deployment is blocked on hosting authorization. There is no live application HTTPS URL yet.** Railway is available but not installed/connected in this session. No Railway project, paid service, domain or deployment was created. Supabase is already connected and healthy. Install/connect the suggested Railway integration to authorize the existing two-service deployment. A paid plan or resource change still requires a reviewed price and authorization before provisioning.

## Implemented and verified

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
| Deployment package | Current Railway IaC/CLI authoring, allowlisted local source upload, server-only variables, health checks, dynamic ports, non-root web container, private dual-stack Python worker | Both actual Docker images built and ran; local container checks are not a public deployment |

## Tests executed

- 209 application TypeScript tests passed across 36 files (10.33 seconds).
- All 26 production-standalone browser tests passed across desktop and iPhone Chromium (37.4 seconds).
- Six focused PWA unit tests and eight focused browser checks passed, including cache-clear recovery.
- Five deployment Node tests and two Python deployment-runtime tests passed.
- Production Next.js build passed after the final PWA changes.
- Eleven live-cloud workflow checks passed, with live AI explicitly reported unavailable.
- Actual backend restart continuity passed for finances, conversations and the signed 10,000-game simulation.
- Both actual deployment Docker images built. Container readiness reached the real Supabase service and private Python worker; anonymous financial access returned 401 and ephemeral SQLite selection returned 409.
- All 24 original SQLite data tables remained unchanged against the consistent pre-release backup; integrity checks returned `ok`.

The prior 42 Python modeling tests and real 50,000/100,000-game audits remain in the retained 4.0 reports. Modeling code was unchanged for this PWA release; those suites were not rerun merely to restate the same result. A 100,000-game run does not establish calibration or market advantage. The model remains research-only and trails the indicative historical market benchmark.

Machine-readable evidence: [PWA checks](reports/pwa-readiness.json), [live cloud workflow and restart](reports/pwa-local-cloud-workflow.json), [original data preservation](reports/pwa-data-preservation.json), [QA cleanup](reports/pwa-live-account-cleanup.json), and [actual Docker checks](../deployment/railway/container-verification.json). Test accounts used reserved `example.test` addresses; no confirmation emails were sent.

## Required external configuration

1. Install/connect Railway. The exact deployment, private-network, source-upload and secret-configuration steps are prepared in [RAILWAY.md](RAILWAY.md). Review the actual account plan and any charge before provisioning. No ephemeral tunnel is presented as a production host.
2. Set server-side Supabase URL/publishable key and preserve the existing simulation token on both services. Do not use a service-role key in the web application. The deployment wrapper pins Supabase storage and the real HTTPS origin.
3. After the domain exists, configure Supabase Auth Site URL and allowed email redirects for that exact HTTPS origin, then verify signup/confirmation using an authorized account. The connected database tooling does not expose an Auth-config mutation. Existing password login was tested; actual email delivery and production redirect behavior were not.
4. Add `OPENAI_API_KEY` through the host's server secrets for live conversation. Never paste it into public source or browser code. Licensed odds or official injury feeds require their own authorized access; manual/CSV/OCR entry remains supported.
5. Run the supplied [full URL workflow](PWA_WORKFLOW_VERIFICATION.md) against the actual deployment, check production logs and HTTPS assets, then perform Safari Share → Add to Home Screen on the user's iPhone.

No signed IPA, App Store or TestFlight release is part of this update. Logical encrypted exports are tested; complete normalized typed-table reconstruction and provider backup/PITR retention retain the limitations documented in [SUPABASE.md](SUPABASE.md).

## Source delivery

The updated source archive is `artifacts/gridiron-ai-pwa-source.zip`, with a matching `.sha256` file. It excludes credentials, financial databases, runtime caches, deployment SDK dependencies and signing material. Saving the ZIP to iPhone Files stores source; it does not execute Next.js or Python. The installed PWA requires the real hosted HTTPS backend.
