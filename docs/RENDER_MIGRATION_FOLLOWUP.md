# Render staging continuation — 2026-11-06

**Status: staging only; migration and production cutover are not complete.**
The existing site is <https://gridiron-ai-frontend.onrender.com>. No service was
created, DNS changed, Vercel disabled, billing changed, or research model promoted.
V24 remains checkpointed at `d4d5fd1c538b188939947942c8772f768f7a0fa5`.

## Release identity and the remaining Render setting

The existing frontend is `srv-dblsg9gn74is73cjc8lg` in workspace
`tea-dbidrq6c6qcc73a7n0u0`, Free, Virginia, one instance, automatic deployments off.
The latest inspected live release is `dep-dbmv9rh5efls738m7oog`, completed at
15:43:11 UTC, source **`3ac16f9710e330b2d486097483264293c5a59336`**.
The service still links to **`main`**. Therefore the migration branch's standalone
startup, release identity, and new request optimization are **not yet hosted**.
Successful environment deployments do not establish that this branch is running.

The connected Render tools can deploy the linked branch and merge environment
variables, but cannot edit the branch or select a source commit. There is no
connected browser-control tool. Make this exact staging-only change:

1. Open <https://dashboard.render.com/web/srv-dblsg9gn74is73cjc8lg>.
2. Select **Settings → Build & Deploy → Branch → Edit**.
3. Enter **`migration/render-stage-v24`**, then **Save**.
4. Keep **Automatic Deploys disabled**, root directory empty, build command
   `npm ci && npm run build`, and start command `npm run start`.
5. Deploy the reviewed branch tip using **Manual Deploy → Deploy latest commit**,
   unless saving has already started that deployment. Do not launch duplicate builds.

After it becomes live, the new `/api/health` response must identify that exact
Git commit and `migration/render-stage-v24`. Inspect startup logs for
`node scripts/start-web.mjs`, not the former `next start` standalone warning.
Run the verifier with the expected remote branch commit:

```sh
VERIFY_BASE_URL=https://gridiron-ai-frontend.onrender.com \
VERIFY_EXPECTED_COMMIT=<reviewed-40-character-commit> \
VERIFY_OUTPUT=artifacts/render-migration-v24/followup-release \
node scripts/verify-render-stage.mjs
```

## Gateway credential repair: deployed and tested

The existing gateway is `srv-dbj680s9v7es7397nv2g`,
<https://gridiron-propline-gateway.onrender.com>. Its linked branch remains
`upgrade/propline-free-props`. A compatible one-file update was published there:
**`3e31d0d851fc23682284bee6e44b9de15ec55e3c`**,
live release **`dep-dbmv8ph5efls738m5ejg`** (15:39:05 UTC).

The original primary token cannot be recovered through the connected tools:
Vercel marks it write-only, and the Render connector has no environment-read
operation. Its existing secure operator source is the gateway's **Environment**
page in Render. No Git file, browser response, or public source is an acceptable
credential source. Bulk Vercel environment listings contain encrypted values and
must not be copied as usable secrets.

An additive coordinated rotation was completed without replacing that primary:

1. Gateway authentication now supports its unchanged
   `GRIDIRON_DATA_BRIDGE_TOKEN` and a separate
   `GRIDIRON_DATA_BRIDGE_STAGING_TOKEN`, with constant-time comparisons.
2. A cryptographically generated staging token was merged into the gateway's
   encrypted environment. The primary key was omitted from that update.
3. The same staging token was merged into the existing frontend's
   `GRIDIRON_DATA_BRIDGE_TOKEN`; the frontend was redeployed.
4. A real authenticated gateway `/metrics` request returned **200**, while the
   same request without credentials returned **401**. NFL, CFB and NBA provider
   calls through the frontend then returned verified provider rows.

The original primary value was not retrieved, printed, replaced or committed.
Unit tests verify legacy and staging-token compatibility. Its continued actual
value is established by the non-replacing update, not a claim that the unreadable
old credential was used for a live probe. Existing Vercel configuration remains
unchanged. Retiring the primary requires a later coordinated client migration;
neither token expires automatically. Do not roll the gateway back to pre-overlap
code while staging still uses the new token.

## Supabase Auth setting and account acceptance gate

Use the existing project only: **`qdtdjbapdipopncklsdb`**. Open
<https://supabase.com/dashboard/project/qdtdjbapdipopncklsdb/auth/url-configuration>.
Under **Authentication → URL Configuration → Redirect URLs**, add:

```text
https://gridiron-ai-frontend.onrender.com
https://gridiron-ai-frontend.onrender.com/
https://gridiron-ai-frontend.onrender.com/auth/callback
```

If the interface normalizes the first two into one root URL, retain that root and
the callback entry. Keep every existing Vercel/production entry and **do not change
the current Site URL** before approved traffic cutover. Save the configuration.
Current code uses the root for its PKCE/confirmation return; the callback is also
explicitly allowed. Existing email templates must honor the requested redirect.

The connected tools cannot inspect or edit this Auth setting. No confirmation of
the new staging allowlist has arrived. Consequently **successful password login,
refresh, logout, reopened-account persistence and email-link delivery have not
been claimed or run in this continuation**. Existing public Auth discovery,
unauthorized-wallet rejection and rollback-only database tests are separate checks.

Two new, uniquely named synthetic QA identities have been provisioned for the
requested acceptance tests. Their random credentials are encrypted locally; no
existing account was updated. Provisioning temporarily reused the existing
validation Edge Function with JWT verification, a fixed two-identity allowlist,
a one-time capability and a ten-minute expiry. Its original disabled body was
restored immediately in a `finally` path, and a real subsequent request returned
**410**. No provisioning capability remains active. These accounts were confirmed
by Admin creation, so they do not test confirmation-email delivery.

After the allowlist is genuinely confirmed, run in this prepared workspace:

```sh
node scripts/run-render-auth.mjs --allowlist-confirmed
node scripts/run-render-auth.mjs --allowlist-confirmed --reopen
```

The initial test refuses non-QA identities and nonempty wallets. It verifies
Secure/HttpOnly cookies, exact test-ledger arithmetic, research revisions,
conversation/preferences persistence, cross-user read/write denial,
refresh-cookie recovery, logout and a new browser context. The second command
performs read-only reopened-account checks. It must not be mistaken for a
physical-device or backend-restart test. Preserve the encrypted fixture files for
resumption; they are excluded from Git and source archives. Do not repeat the
initial financial writes against an already initialized QA wallet.

## Persistence, isolation and recovery

- The real Supabase rollback test passed again: starting 100.00 + deposit 50.00 −
  withdrawal 20.00 − wager 10.00 + actual return 19.00 = **139.00 cash**, **9.00
  realized betting P/L**, **0 pending exposure**. Deposits/withdrawals were not
  betting profit/loss. Research create/edit/retrieval reached revision 2.
- A second authenticated database role could not read the first role's ledger or
  workspace. All test writes and both transaction-scoped users rolled back;
  final absence checks passed. These are managed-database role/RPC tests, not HTTP
  login or cross-device acceptance.
- Eleven original private-table counts and content digests matched before and
  after staged checks, excluding only the two newly created synthetic QA IDs.
- All inspected public tables still have RLS enabled (zero without RLS). No
  service-role key was added to the frontend or browser.
- The existing encrypted recovery export, receipt and separate key retain their
  original checksums and restrictive permissions. The earlier 21-table logical
  export and byte-equality decryption check remain intact.
- This is not proof of complete Auth/Storage/PITR backup coverage, off-host key
  custody, or a successful full database restore. Those remain recovery gates.
- Latest database size was **469,259,955 bytes**. Capacity remains tight; no cleanup,
  schema reset, financial deletion, or unnecessary large data copy was attempted.

## Actual sport, provider and research checks

| Feature | Actual staging result |
|---|---|
| NFL schedules | 200, 59 games, nflverse provenance |
| CFB schedules | 200, 130 games, ESPN provenance |
| NBA schedules | 200, 23 games, ESPN provenance |
| NFL PropLine board | 200, 500 frontend rows sampled; first 50 also checked directly at gateway |
| CFB PropLine board | 200, 500 frontend rows sampled; first 50 also checked directly at gateway |
| NBA PropLine board | 200, 500 frontend rows sampled; first 50 also checked directly at gateway |
| DraftKings Sportsbook | Present in all three provider samples, explicitly sportsbook reference data |
| DraftKings Predictions | Unavailable: `feed_not_configured`; zero authorized contracts verified |
| NFL/CFB archived learning research | Actual APIs returned 200 and archived records |
| Shared evidence persistence | Existing returned research pointers reported saved; no fabricated new distributions |
| Independently publishable/calibrated board probabilities | **Zero in these samples**; existing quality gates correctly withhold failed/unsupported evidence |
| Conversational AI generation | Missing `OPENAI_API_KEY`; not executed or silently substituted |
| Apple sign-in | Not configured; email/password provider discovery works |
| MongoDB/R2 | Absent from audited deployment configuration; no connection/migration claimed |
| Injury/lineup evidence | Partial; unresolved identities, unavailable-player evidence and unfitted availability scenarios remain explicit blockers |

At the 15:38 provider observation, the feed reported these inventories (not
additional full-board end-to-end samples):

| League | Validated inventory reported by adapter | DraftKings rows | Nonzero categories reported |
|---|---:|---:|---|
| NFL | 14,169 | 1,442 | Passing yards/TD/attempts/completions/INT, rushing yards/attempts, receiving yards/receptions, anytime TD |
| CFB | 3,412 | 763 | Passing yards/TD/attempts/completions, rushing yards, receiving yards/receptions, anytime TD |
| NBA | 8,536 | 1,173 | Points, rebounds, assists, threes, steals, blocks, PRA, double-double |

Other reported books included FanDuel, BetMGM and Hard Rock. The observed provider
quota header was 5,000 requests/day; this is the configured entitlement observed
in responses, not a subscription change. No claim is made that every endpoint or
historical product is authorized.

`quotedAt` was null: these are provider-observed sportsbook prices, not verified
executable quotes. Fees, exact settlement exceptions and execution remain
unverified. Selection-only anytime-TD rows do not acquire an invented numerical
threshold. No line is relabeled as a DraftKings Predictions event contract.

Existing football distributions were rejected for availability/accounting
inconsistency, unsupported player/event crosswalks or unsupported availability
mixtures. NBA rows remained sportsbook reference data. Migration work does not
weaken these gates, claim the simulations passed, manufacture percentages or
promote research candidates. Forecasting repair requires the separate evidence
and mechanical-validation campaign.

## Separate simulation worker connection

The existing durable Supabase compute RPC was reached using its existing stable
capabilities. A read-only preflight returned `cache_and_queue_only`, concurrency
**1**, daily job limit **6**, daily trial budget **100,000**, and daily worst-case
job-time budget **1,800 seconds**. **Zero jobs were claimed; zero simulations ran.**
No continuous worker or new cloud resource was started.

The worker now requires `GRIDIRON_COMPUTE_ROLE=worker`, refuses both existing web
service IDs, and rejects web-service/Vercel invocation. HTTPS queue connections
will not redirect bearer capabilities to another origin. The web startup enforces
its own web role even if the environment incorrectly says worker. Budgets, leases,
process-group supervision and the existing durable queue remain intact.

Operator configuration for an already authorized local/background execution host:
`SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY`, `GRIDIRON_PUBLIC_INGEST_TOKEN`, and
`SIMULATION_SERVICE_TOKEN`. Transfer those securely, never through Git or browser
settings. Set the explicit worker role and request-lifetime flag, then:

```sh
GRIDIRON_COMPUTE_ROLE=worker GRIDIRON_WORKER_REQUEST_LIFETIME=0 \
python scripts/compute-worker.py --preflight
```

Only a separately authorized controlled invocation should claim jobs. It starts a
loopback Python endpoint for each admitted task; it does not need the frontend to
run Python. No hosted quantitative-worker URL or persistent consumer was verified.
The preflight is connectivity/policy evidence, not model-execution evidence.

## Code changes and measured performance

The migration continuation adds the overlapping gateway credential, safe release
identity in health responses, read-only worker preflight, secret-free stdin
verification clients, encrypted QA fixture preparation and guarded acceptance
tests. `tsconfig.json` excludes ignored QA artifacts from the Next build; generated
Deno helper code must not become application type-check input.

The football board previously repeated the same game-wide integrity/availability
audit for every prop. A **request-scoped**, immutable-snapshot memo now reuses
that result within one response. New evidence or a different injury snapshot
cannot reuse it. There is no longer-lived freshness extension or change to model
math, simulation counts, distributions, injury exclusions or calibration.
Queued UI rows say **Waiting for worker** and failed simulations say **Simulation
failed**; the interface no longer claims queued work is actively calculating.

Five alternating synthetic 500-row benchmark rounds measured average audit-path
CPU **118.249 → 6.411 ms** (about **94.6%** lower for this isolated workload), wall
time **112.368 → 5.963 ms**. Serialized outputs had identical SHA-256 hashes.
**This is not a measured whole-application, hosted-billing or predictive-accuracy
improvement.** No simulation was run for that benchmark.

Actual hosted observations after the gateway repair:

- Sampled peak frontend memory: **270,684,160 bytes** (about 258 MiB), below the
  512 MiB Free instance limit. Sampled peak CPU: **0.09887 cores**. These are
  observations during bounded checks, not sustained-load guarantees or billed
  CPU-seconds. Platform p95 HTTP latency was unavailable.
- Initial 500-row API loads: NFL **11.29 s**, CFB **27.71 s**, NBA **10.59 s**.
  iPhone-size Prop pages took **14.40/24.63/17.84 s** respectively. These delays
  remain limitations; repeated calls after expiry are not presented as warm hits.
- Read-only homepage/PWA browser checks: iPhone-size **9.72 s**, desktop **2.78 s**.
  The previous checkpoint observed a **51.31 s** Free-instance cold response.
- The prepared local standalone process reached HTTP in **602 ms**, RSS **155,040
  KiB**, with no standalone warning. Public assets and guest-wallet denial passed.
  This local start used synthetic configuration and performed no external writes.
- No application error logs were returned for the inspected 15:43–16:02 UTC
  post-release window. Live frontend source remains the older main commit.

The instance plan remains $0/month. Free idle sleep, workspace-shared running
hours, quotas and external provider limits remain relevant. No keep-alive loop,
new paid worker or increased plan was introduced.

## Tests executed and precise untested scope

- **791 Vitest tests**, 114 files, passed.
- **42 Python tests** passed together: bridge rotation, worker preflight,
  BALLDONTLIE regression and football provider adapters.
- **2 Node hosting tests** passed: safe hosted boot and public standalone assets.
- Final production build/type-check passed. Build metrics are recorded in the
  companion verification JSON; build-host memory is separate from web memory.
- Real Supabase rollback accounting, workspace-version and RLS isolation tests
  passed; final absence checks passed.
- iPhone-size and desktop guest browser/PWA/offline checks passed. All three
  sport boards returned 500 actual rows on mobile, with no JavaScript errors or
  horizontal overflow. Seven cached public assets and no private API cache
  entries were observed. No physical iPhone/Safari installation test occurred.
- The disposable HTTP login/session/logout/private-reopen test is implemented
  but remains **pending allowlist confirmation**. Confirmation email delivery,
  physical cross-device persistence and persistence across a new migration-code
  deployment are not verified by the preceding database tests.
- No expensive research workload, 10,000-game run, new model validation or
  production promotion was performed during this migration continuation.

## Rollback and remaining cutover gates

Retain [the original checkpoint's recovery procedure](RENDER_MIGRATION_V24.md).
Keep Vercel, DNS and the production branch untouched. Render application rollback
must not restore or reset databases. The existing encrypted export/key stay
private and unchanged.

For the frontend, the current pre-branch-change fallback is source `3ac16f9` /
release `dep-dbmv9rh5efls738m7oog` with persistent Supabase and the staging gateway
token. Record the tested migration commit before manual staging deployment.
On failure, roll back application source while retaining the cloud-only database
settings and gateway overlap. Do not re-enable an ephemeral SQLite wallet.

For the gateway, keep the dual-token-compatible release while either client uses
the staging token. A later retirement/reversal requires coordinating both clients
through the secure Environment UI. Never invent or replace the unreadable primary.

Remaining critical gates: correct migration-branch deployment; Auth URL
confirmation and actual disposable-account login/session/logout/reopen acceptance;
provider-level backup/recovery confirmation; honest handling of unavailable AI,
event-contract feeds and model/worker evidence. A live homepage and successful
build alone do not authorize cutover. Present exact domain changes and rollback
steps for explicit approval only after the critical checks pass.
