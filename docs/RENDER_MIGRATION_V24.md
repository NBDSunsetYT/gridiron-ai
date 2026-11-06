# Render staging migration — V24 checkpoint

**Follow-up:** see [the staging continuation report](RENDER_MIGRATION_FOLLOWUP.md)
for the November 6 gateway repair, actual three-sport provider checks, worker
preflight, updated measurements, and remaining branch/Auth gates. The acceptance
table below records the earlier checkpoint; it is not the latest provider status.

V24 research was checkpointed separately at `research/dynamic-v24`, commit
`d4d5fd1c538b188939947942c8772f768f7a0fa5`. No research candidate was promoted.
This compatibility branch starts from production commit
`3ac16f9710e330b2d486097483264293c5a59336`; it does not include V24 models.

## Existing service and recovery path

Use **gridiron-ai-frontend**, `srv-dblsg9gn74is73cjc8lg`, workspace
`tea-dbidrq6c6qcc73a7n0u0`, Virginia, **Free**, one instance, automatic deployment off.
Do not create a duplicate service. Staging URL:
<https://gridiron-ai-frontend.onrender.com>.

The previous live deploy was `dep-dblsg9on74is73cjc98g`, production source `3ac16f9`.
It built successfully but was unconfigured: SQLite, no Supabase/AI/model connection,
and a warning that `next start` is incompatible with standalone output. No POST,
PUT, PATCH or DELETE requests were returned by the service's available request-log
query from creation through the initial audit. This is log evidence, not a full
forensic backup of the ephemeral filesystem.

Vercel's `gridiron-ai` project and all DNS settings remain unchanged. Its project ID
is `prj_ufIV2AZJcQAW7lNtQmH6hcyrWamH`, team `gridiron5`. Preserve its configuration
and paused deployment as the rollback reference; do not resume the older Python
request-compute architecture or switch traffic automatically.

## Exact build and startup

Keep the service commands **`npm ci && npm run build`** and **`npm run start`**.
This branch makes those commands stage public/PWA assets and versioned static
chunks in `.next/standalone`, then run its generated server directly. The process
binds `0.0.0.0` and Render's `PORT`, and directly receives termination signals.
`NEXT_DIST_DIR` is supported for isolated local builds.

Render startup fails closed when persistent Auth configuration is absent. The web
entry point always selects Supabase and `GRIDIRON_COMPUTE_ROLE=web`; it never starts
a model worker, local ledger migration, scheduler or training process. Existing
bounded workers remain separate. `python scripts/compute-worker.py --dry-run`
inspects their limits without running jobs. Do not run workers from `npm start`.

## Environment inventory

All application credentials are **server-side**; there are no required
`NEXT_PUBLIC_*` secrets or browser Supabase keys in this architecture. The audited
code accesses server settings at runtime. `.env.example` remains the full optional
configuration catalogue. The private audit indexes all 93 Node environment names
and referencing source paths under `artifacts/render-migration-v24`.

| Group | Variables | Requirement |
|---|---|---|
| Auth/personal storage | `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY`, `DATA_BACKEND=supabase`, `GRIDIRON_CLOUD_ONLY=1` | Required; existing project `qdtdjbapdipopncklsdb` |
| App identity | `APP_URL=https://gridiron-ai-frontend.onrender.com` | Required; no localhost or Vercel redirect on staging |
| Compute isolation | `GRIDIRON_COMPUTE_ROLE=web`, `GRIDIRON_ASYNC_SIMULATIONS=1`, `GRIDIRON_WORKER_REQUEST_LIFETIME=0` | Required web policy; enforced again at startup |
| Shared cache/queue | `GRIDIRON_PUBLIC_INGEST_TOKEN` | Stable existing capability, never regenerate during migration |
| Signed historical artifacts | `SIMULATION_SERVICE_TOKEN` | Preserve exactly; rotation can invalidate prior receipts |
| Separate quantitative worker | `SIMULATION_SERVICE_URL` | No existing hosted quantitative worker was found; keep controlled local workers separate from this frontend |
| Licensed-data gateway | `GRIDIRON_RENDER_DATA_URL`, `GRIDIRON_DATA_BRIDGE_TOKEN` | Existing gateway; token is write-only in Vercel and requires secure transfer |
| Assistant | `AI_PROVIDER`, `OPENAI_API_KEY` or supported `AI_GATEWAY_API_KEY` | Existing configuration selects OpenAI, but no provider key was available in Vercel's stored settings |
| Native registration encryption | `DEVICE_TOKEN_ENCRYPTION_KEY` | Preserve, no rotation |
| Operators | `CRON_SECRET` | Preserve; no cron service is created or enabled here |
| Optional Atlas | `MONGODB_URI`, `MONGODB_DATABASE`, `GRIDIRON_MONGODB_RESEARCH` | Not present in the audited Vercel environment; no database migration |
| Optional R2 | `R2_ACCOUNT_ID`, `R2_BUCKET`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `CLOUDFLARE_R2_ADMIN_TOKEN` | Not present in audited Vercel environment; private archive access remains unverified |
| Optional event contracts | `GRIDIRON_DK_PREDICTIONS_FEED_URL`, `GRIDIRON_DK_PREDICTIONS_FEED_TOKEN`, `GRIDIRON_DK_PREDICTIONS_FEED_AUTHORIZED` | No authorized feed configured; never replace with sportsbook prices |

The bulk Vercel API returned encrypted envelopes even when decryption was
requested. The first staging probe rejected those unusable values; individual
decrypted-variable retrieval repaired the transfer. Do not copy ciphertext from a
bulk environment listing. Sensitive write-only variables cannot be recovered by
that method. No credentials belong in Git, logs, client requests or this report.

Supabase Auth must **add** the exact Render return URLs to its allowlist while
retaining the existing production Site URL until cutover approval. Review email
templates for `.RedirectTo` handling. No Auth settings or accounts were reset.
Apple sign-in is only offered if Supabase reports it configured.

## Architecture and preservation checks

- Next.js 15 / React 19 remain server-rendered. API middleware, ownership checks,
  security headers, HttpOnly sessions, and private/no-store APIs are retained.
- All inspected public database tables have RLS enabled. Financial data remains
  in Supabase. No schema migrations, table resets, credential rotation or data
  transfers are needed for this hosting change.
- MongoDB public research and private R2 archives remain optional adapters; do not
  claim them connected without credentials and read/write tests.
- PropLine credentials remain on the existing Python data gateway. Exact DraftKings
  Predictions contracts remain a separately authorized product, not sportsbook odds.
- The old CFB Runtime Cache adapter is Vercel-only and guarded by `VERCEL=1`.
  Supabase shared cache/published records remain the durable source on Render;
  process-local caches and single-flight work are bounded optimizations only.
- User accounts, financial records, forecasts and conversation history never rely
  on this Free service's temporary filesystem. Temporary build files and caches
  can disappear on restart. Do not store essential jobs or models there.
- The service worker caches only static public assets and the offline shell.
  Authenticated HTML and API replies are excluded. Icons, safe areas and deep
  links are preserved. Physical Safari installation is a separate device test.

Two existing encrypted recovery archives were verified to exist in the private
checkpoint table (latest 2026-10-31). A fresh repeatable-read export of 21 selected
private row tables was additionally encrypted locally with AES-256-GCM and gzip,
then decrypted and compared byte-for-byte. It contained 1,408,511 plaintext bytes,
82,320 compressed bytes. The 600-mode key and encrypted archive are excluded from
Git. This does **not** verify full Auth, Storage/PITR coverage, off-host recovery or
a full database restore. Provider backup confirmation remains a cutover gate.
The existing financial, conversation and research table counts and content
digests matched across the staged deployment and rollback-only QA tests.

The deployed Supabase QA transaction tested starting balance 100.00, deposit 50.00,
withdrawal 20.00, a 10.00 wager and actual return 19.00: cash **139.00**, realized
betting P/L **9.00**, exposure **0**. Research write/update/retrieval and cross-user
RLS checks passed. The transaction rolled back, and both synthetic users and the
test workspace were confirmed absent. These are real database role/RPC checks,
not a claim that browser login or cross-device account persistence passed.

## Reproducible checks

```sh
node --test scripts/test-render-hosting.mjs
npm run build
npm run start
VERIFY_BASE_URL=https://gridiron-ai-frontend.onrender.com node scripts/verify-render-stage.mjs
```

The browser script is read-only. Real private write-path and cross-device tests
require explicitly provisioned disposable QA identities. Never run the existing
financial QA scripts against a real account; they assert an empty synthetic
workspace before adding transactions.

Initial Free-service cold response was **51.31 s**; warmed asset/API responses were
**0.13–0.39 s**. Observed idle memory was **172,421,120 bytes** versus a
**536,870,900-byte** limit. Local compatibility build passed in **61.65 s**,
**103.03 CPU s**, peak RSS **1,386,348 KiB** (build host, not web runtime).
The prepared local standalone server started in **207 ms**. These are measurements,
not guaranteed availability or billing forecasts. CPU metrics were initially empty;
no 70–90% savings claim is made. Existing instance price remains **$0/month**;
sleep, build quotas, included usage and external-provider limits still apply.

Render's current Free documentation confirms 15-minute idle sleep, ephemeral
filesystems and **750 running instance hours per workspace/month**, shared across
Free web services. The existing frontend and gateway both use that pool. No
keep-alive service, paid worker, plan change or billing change was introduced.
Bandwidth/build overages depend on the account's existing limits and payment
configuration; $0 instance pricing is not a guarantee of zero total usage charges.

## Executed staging acceptance results — 2026-11-06

The corrected environment release **`dep-dbmo0f3m8hqs73b09q2g`** is live on source
**`3ac16f9710e330b2d486097483264293c5a59336`**. The startup/package changes on this
migration branch are locally verified and **not yet deployed**: the service still
links to `main`, and the connected tool cannot edit that setting.

| Check | Actual result |
|---|---|
| HTTPS homepage, API routes, deep links | Passed on the deployed Render URL |
| Supabase deep readiness | HTTP 200, `reachable`, intended project |
| Web compute policy | `cache_and_queue_only`; no simulation executed by these checks |
| NFL schedule | HTTP 200, 59 games, nflverse source/version recorded |
| CFB schedule | HTTP 200, 130 games, ESPN source; licensed enrichment unavailable |
| NBA schedule | HTTP 200, 23 games, ESPN source |
| Mobile/desktop NFL, CFB, NBA, simulations/reality navigation | 8 additional checks passed, no browser errors, overflow or write requests |
| Manifest, 192/512 icons, Apple icon, service worker | HTTP 200; service worker activated |
| Offline shell | Both browser sizes passed; seven public cached assets, no private API cache entries |
| Auth provider discovery | Email/password available; Apple unconfigured |
| Wallet guest access | HTTP 401, private/no-store |
| Cross-origin mutation | HTTP 403 |
| Guest logout | HTTP 200, Secure/HttpOnly cookie clearing |
| Invalid password | HTTP 400, rejected by Auth |
| Invalid confirmation callback | HTTP 303 to this Render origin's `/auth/error`, secure cookie clearing |
| Successful account login, refresh, reopen, cross-device history | Not executed; disposable QA credentials and Auth allowlist verification required |
| Production Supabase transaction/RLS test | Passed, completely rolled back; no synthetic users or workspace remain |
| Local financial regression | Exact fees/payouts, legacy preservation, isolation, export/import and duplicate retry passed |
| Hosting regression | 22 Vitest checks across five files and two Node hosting tests passed |
| Local production standalone build | Passed, static and PWA assets served at their correct paths |
| Original private record preservation | 11 table counts/content digests matched before and after staging checks |
| Licensed data gateway | HTTP 200 `ready`; explicitly `providerAccessVerified=false`; 32.31-second cold request |
| NFL/CFB PropLine prices | Unavailable on frontend until existing gateway bridge token is securely supplied |
| DraftKings Predictions contracts | Zero authorized contracts verified; diagnostic `feed_not_configured` |
| Conversational AI generation | Unavailable: `OPENAI_API_KEY` missing; no generation or purchase attempted |
| Hosted simulation worker | No configured `SIMULATION_SERVICE_URL` or separate quantitative service found; controlled local runner retained |
| MongoDB/R2 credentials | Absent from audited Vercel environment; no migration or deletion attempted |
| Latest application error logs | Only the intentionally tested unconfigured Apple provider returned 503 in the inspected post-repair error window |
| Physical iPhone installation | Not performed; Chromium iPhone-size checks only |
| DNS/Vercel/production models/billing | Unchanged |

Observed Render memory during the inspected window was at most **210,726,910
bytes** (about 201 MiB), below the 512 MiB instance limit. Sampled CPU peaked at
**0.06273 cores** in startup/request windows; this is not billed CPU seconds or a
before/after savings measurement. Platform p95 HTTP latency was unavailable.
Warm browser verification took **2.95 s** at iPhone size and **1.66 s** desktop;
individual warm static/guest API probes took **52–144 ms**. Real schedule probes
took **0.74–2.82 s**, and the deep Supabase check took **1.77 s**. These are small
controlled samples, not sustained load or uptime validation.

The new Render URL works for guest schedules, but **the migration is not complete
and is not ready for production cutover**. Remaining critical gates are the
reviewed startup branch deployment, gateway token, real account acceptance,
authenticated private persistence, actual worker/AI/provider configuration and
provider-level recovery confirmation.

## Cutover gate and rollback

Keep automatic deploys off. The connected Render tool can merge environment
variables and deploy the linked branch; it cannot change that branch/start command
or deploy a specific commit. To stage this code without changing production main,
link this existing service to **`migration/render-stage-v24`**, then deploy its
reviewed commit. Do not create a Blueprint/duplicate service as a workaround.

Before proposing traffic cutover, require real Render tests for login/logout,
session refresh, owned read/write/reopen, financial reconciliation, all three
sports, source freshness, provider failure states, deep links and PWA assets. A
successful build and a public health response alone do not satisfy acceptance.

If validation fails, leave Vercel/DNS untouched. Revert this service to the retained
known source/deploy and its recorded server settings, preserving Supabase/cloud
data and stable keys. A Render application rollback does not roll back databases.
Do not restore SQLite as a new personal-data store on ephemeral hosting.

**No DNS/domain change, Vercel disabling, production-model promotion, paid resource
or production traffic cutover is authorized by this staging checkpoint.** Present
the exact proposed domain changes and rollback steps for explicit confirmation
only after all critical checks pass.
