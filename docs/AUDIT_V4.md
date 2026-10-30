# GRIDIRON AI 4.0 evidence audit

This audit separates working code, actual external checks and release limitations. It supersedes current-capability claims in the retained historical 2.0 reports without rewriting those records.

## Baseline-to-current inventory

Status labels describe the delivered scope: **Working** means implemented with corresponding executed evidence; **Partially implemented** means useful behavior exists with stated gaps; **Missing** means the capability is not delivered/connected; **Unverified** means source or configuration exists but the required runtime check has not occurred. The preserved 2.0 release used Next 15/React 19 and recorded 82 TypeScript/21 Python tests; those historical counts are not the current suite.

| Capability | Baseline 2.0 | Current 4.0 | Evidence or remaining gap |
| --- | --- | --- | --- |
| Next/React responsive application | Working | Working | Production build and desktop/iPhone Chromium workflows |
| Durable SQLite, scrypt/session authentication | Working | Working | Explicit preserved workspace; all 24 pre-existing tables/original columns unchanged |
| Exact-money ledger/PWA | Working | Working | Exact balanced financial operations; install assets and offline browser checks, separate physical-iPhone boundary |
| OpenAI adapter/private play-by-play service | Partially implemented | Partially implemented | Integration source and historical simulator work; live OpenAI missing credentials; actual cloud 10k fit/simulation persistence passed on real retrospective data |
| Manual markets/injuries | Working | Working | User-verified input/provenance; this does not establish an official live feed |
| Supabase Auth/PostgreSQL/RLS | Missing | Working | Configured live project, 24 API checks, all 47 public tables with RLS, owner isolation |
| Native iPhone application | Missing | Partially implemented / Unverified | Real source/project preparation and cap sync; Swift compilation, signing, IPA and device checks unavailable on Linux |
| Advanced statistical candidates/ensemble | Missing | Partially implemented | Actual 816-holdout research report; market comparison underperformance and unverified timing prevent production promotion |
| Direct DK Predictions/official injury feeds | Missing | Missing | Authorized live feeds/credentials not connected; manual input remains available |
| Full typed cloud export | Missing | Working | All 43 table families included and reconciled in actual encrypted export |
| Complete typed restore reconstruction | Missing | Partially implemented | Finances/compatible histories imported; complete typed payload retained, normalized-table reconstruction incomplete |
| Public HTTPS web hosting | Missing | Missing | Deployment guides/source supplied, frontend not deployed |
| APNs delivery | Missing | Missing / Unverified | Registration source exists; APNs sender/credentials and actual delivery not tested |

## Observed repairs during the upgrade

The upgrade repaired scenario-mixture uncertainty handling, numeric-signature behavior across a JSON hop, a UI path that could report logout success despite failure, and overtime-safety trace logging. These are observed defects with targeted verification, not invented failures attributed to every 2.0 deployment. The large cloud-payload transport defect was repaired with lossless gzip for large input/result leaves, SHA/byte/decompression bounds, a 60-second provider deadline, disabled ambiguous SDK POST retries and owned model-job references. The middleware permits bounded transport without removing the route evidence limit. The real cloud 10k fit/run/read-back path subsequently passed; no local-only test was used as a substitute.

The final fixes also include complete conversation/history pagination above 1,000 messages and lower provider row caps, 503-refresh preservation of already rotated Auth credentials, and retry-safe injury-queue partial-save recovery, idempotence and practice-change handling. Replay dispatch strips audit-only references/mixture recipes only on valid replays; unsupported injury evidence remains blocked rather than receiving invented weights. Seven targeted queue regressions and the full 193-test TypeScript suite passed. The fifth additive live migration restores saved-research/watchlist namespaces with idempotence and invalid-kind rollback, retaining the original archive and all four earlier migrations unchanged.

## Cloud persistence and security

A real Supabase project is configured and all five additive migrations are applied. Live SQL/RLS/ledger rollback fixtures passed again after migration five. Live password sessions and PostgreSQL financial operations were exercised through the local Next backend. The report contains 19 primary plus 5 additional passing checks, covering anonymous rejection, scoped access, exact financial RPC behavior, imports, owned histories, refresh/restart continuity, logout revocation and confirmed owner deletion. This establishes a tested cloud backend, not a deployed HTTPS web frontend.

Live PostgreSQL metadata verified RLS enabled on all 47 public tables. RLS and ownership are database controls in cloud mode; preserved SQLite mode uses application ownership guards. A publishable key does not grant administrative access. Browser cookies are HTTP-only; server APIs verify identity. Admin credentials stay in the Edge Function boundary, not browser/native source. No claim is made that local unit tests alone establish remote RLS correctness: the separate live report supplies that evidence.

The final remote security advisor reported one warning: `auth_leaked_password_protection` is disabled. No SQL/RLS finding was reported. The optional leaked-password check can be enabled in the Supabase dashboard if supported by the project plan; available tooling did not expose a configuration mutation. Do not describe the final advisor result as zero findings.

The read-only [legacy preservation audit](reports/v4-legacy-preservation.json) fingerprinted all 24 pre-existing SQLite tables using their original columns against the consistent pre-v4 snapshot. It found no changed rows and integrity checks returned ok before/after. This is stronger continuity evidence than an empty-workspace migration test; the report excludes private row contents.

## Backup completeness versus restoration

The executed export includes all 43 normalized owner-scoped table families, 149 actual normalized plays and 285 actual recorded games. Pagination counts and raw financial reconciliation were verified, and passwords/sessions are excluded. The archive preserves typed source payloads.

The current importer restores financial/compatible app histories and archives the complete typed payload, but full normalized-table reconstruction is incomplete. **Complete export is not complete typed restore.** Provider backup/PITR configuration and retention were not verified. The tested encrypted logical export is a separate capability. Keep project-level backups and original encrypted archives; use a verified database restore or deliberate typed importer to recover normalized NFL/model tables. See [SUPABASE.md](SUPABASE.md) and [MIGRATIONS.md](MIGRATIONS.md).

## Real warehouse coverage

Actual public nflverse schedules and one game's play data were ingested/read back in disposable QA owners with owner RLS and duplicate-safe retries. Those checks establish importer coverage. Both disposable QA Auth owners and their fixtures were subsequently removed through the authenticated Edge Function, with zero fixture users verified by live SQL; a production owner imports its own source data. 149 retained plays are a normalized subset of 179 source records, with exclusions reported. Games with unknown historical availability retain null. An available current historical file is not proof of point-in-time publication. Source citations, hashes, collection and event times remain material. See [WAREHOUSE_PBP.md](WAREHOUSE_PBP.md) and [report](reports/v4-warehouse-live.json).

## Model performance and promotion

The research suite fits Bayesian, regularized and boosted home-win candidates with a calibrated ensemble. It uses nested chronological tuning, distinct calibration/stacking partitions and 816 untouched rolling annual holdout games. Ensemble Brier 0.224483 improves on the training-home baseline 0.248309, but underperforms the indicative normalized historical market 0.210157. The paired ensemble-minus-market Brier interval is approximately [0.009001,0.019888]; positive means worse.

The market comparison is indicative because quote timing, historical revisions and exact settlement compatibility are unverified. No market feature is used to manufacture independent-model performance. Holdout results do not validate player props, roster/weather adjustments or fitted play-by-play simulation. Model-family/parameter intervals do not include all structural uncertainty. The report explicitly returns `productionEligible: false`, `status: research_only`. No model is promoted as a production wagering signal or guaranteed profitable system.

Evidence: [v4-model-benchmark.json](reports/v4-model-benchmark.json). Earlier total/play-by-play diagnostics are retained separately. Synthetic fixtures verify arithmetic and control flow; they are not historical model results.

## Enhanced complete-game modes

The [real-data simulation audit](reports/v4-real-simulation-modes.json) fitted the enhanced recency/shrinkage engine from 25,303 actual normalized historical plays. It generated 50,000 complete games in 31.113 seconds and 100,000 in 63.120 seconds, with joint/histogram counts, linked passing/receiving trace invariants and convergence checks. These generated games are not 50,000/100,000 independent historical validation cases. The speed-run parameter interval is null, and Monte Carlo error does not estimate parameter/structural uncertainty. No live forecast, calibration or market advantage is established by throughput.

## Connected cloud research verification

The [actual cloud integration](reports/v4-cloud-model-integration.json) used Supabase Auth/PostgreSQL, the authenticated Next API and the private Python service with 25,303 real historical plays. A signed fitted artifact survived JSONB round-trip, 10,000 complete games and 1,000 game-block parameter-bootstrap games were generated, and the attested result persisted and reopened. Exact threshold/equality and shared passing/receiving identities were checked; financial records were unchanged. Parameter uncertainty and Monte Carlo error are separate. This is connected cloud research on retrospective evidence, not a current live forecast or proof of market advantage. Unknown historical availability stays explicit.

## Mobile and release boundary

The native source is a real Capacitor/Swift Xcode project with Keychain/session and navigation safeguards, source preparation and plugin synchronization checks. Linux provides no Xcode/iOS SDK or Apple signing chain, so no Swift compilation, physical Keychain verification, signed IPA, APNs delivery or install is claimed. A Mac, compatible Xcode, Apple team/provisioning and actual HTTPS origin are required. No App Store/TestFlight publication occurred. See [NATIVE_IPHONE.md](NATIVE_IPHONE.md).

PWA desktop/iPhone Chromium coverage is distinct from physical Safari installation. Optional encrypted offline snapshots are read-only/device-local and do not turn an iPhone into a Node/Python backend. Private API responses are not service-worker cached.

## Final verification checkpoint

Reported current suites: 193 TypeScript tests across 33 files in 9.17 seconds, 42 Python tests, PostgreSQL checks passed. Python unittests primarily exercise explicitly marked synthetic mechanics/service fixtures; real historical evaluations are separate reports, and test-suite success is not forecast validation. The final standalone-runtime Playwright rerun passed all 22 desktop/iPhone Chromium tests in 29.9 seconds using Docker-equivalent assets; the latest production build passed all routes after final code repairs. All five migrations are applied live, the fifth function was verified, and final SQL still showed RLS on all 47 public tables. Physical Safari/native-device verification remains separate. The actual 10,000-game cloud-service integration also passed with 1,000 parameter-bootstrap games and persisted result attestations, as separately reported. Live direct DK Predictions, official injury feeds, OpenAI responses and APNs delivery remain credential-dependent/unconnected. The frontend has not been published to a live HTTPS host.
