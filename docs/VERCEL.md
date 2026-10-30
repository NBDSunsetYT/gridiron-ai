# Vercel frontend and API deployment

The existing Next.js/React app stays intact. Vercel hosts its frontend and authenticated Node API; the existing Python/FastAPI engine runs as a private Vercel Service while Render account verification is blocked. Supabase Auth/PostgreSQL remains the durable account database. No native IPA, App Store or TestFlight release is part of this deployment.

## Current verified account and scope

The connected Vercel user is on the **Hobby** plan. The authorized team scope is `gridiron5`, ID `team_GWp3QPUQgohJPqe7ppe9pYmS`. Its initial HTTP 403 was resolved through Vercel's explicit team-authorization flow; a subsequent scoped project read succeeded. No different scope was used to bypass the requirement.

The existing-project inspection returned no projects, so one project named `gridiron-ai` was created: `prj_ufIV2AZJcQAW7lNtQmH6hcyrWamH`. Node 22.x, Fluid Compute and a 300-second function timeout were selected without paid resource upgrades. Existing Supabase keys and the stable simulation token were transferred into encrypted server environment variables without printing values. The atomic frontend/API/private-Python production deployment is READY at https://gridiron-ai-gray.vercel.app, deployment `dpl_75gXVpd768F6Su44YesvG2HSkbJR`. Native build logs verify both Next.js and Python builds; the production dependency endpoint reports Supabase and the private simulation service reachable. See `docs/reports/vercel-production-deployment.json` for the exact provider and HTTP checks. A passing health check does not establish a completed simulation or live AI response.

## Build and runtime settings

- Framework preset: Services; web service framework: Next.js; quant service framework: FastAPI. Both service roots reference this existing application directory. Python is pinned to 3.12 at the project and modeling roots without moving the original engine. The existing backend-routing middleware uses the supported Node runtime because Vercel Services rejects Edge middleware.
- Install: `npm ci`; build: `npm run build`; output directory: framework default.
- Node: supported 22.x or 24.x.
- Use Hobby/default build resources and Fluid Compute; no turbo build, paid memory or multiple-region upgrade is requested.
- `vercel.json` caps API functions at 300 seconds, the current Hobby Fluid Compute maximum. Route-level `maxDuration` exports must also remain at or below that limit.
- `.vercelignore` excludes local credentials, financial databases, caches and native source from CLI uploads. It retains the three historical JSON reports actually imported by the web components.

Current official Vercel documentation states that **both request and response bodies are limited to 4.5 MB**. Increasing Next's middleware limit does not raise that gateway limit. Signed fitted artifacts can be larger. Use owned model-job references and compact server responses instead of resending or returning entire multi-megabyte artifacts in ordinary API JSON. A local Docker pass does not test this platform gateway constraint.

## Private Python service and Render limitation

Vercel Services is **Beta on all plans**. `vercel.json` declares a web-to-quant binding that supplies `SIMULATION_SERVICE_URL` at runtime. The only public ingress rewrite targets the web service. The Python compute service has no public rewrite and additionally checks the retained server bearer token and a short-lived authenticated user session.

Simulation requests first save immutable, owner-scoped inputs and a signed input receipt in Supabase. A 202 receipt identifies the durable job. Next.js `after()` retains the request lifetime while the private Python request performs the actual computation and saves its signed result. Polling retrieves the saved state, verifies the result proof, and shows results only when completed. Vercel request-bound execution does not depend on a detached thread surviving after its response. The 300-second Hobby timeout applies; a timed-out job preserves its inputs for an explicit fresh-session retry. A model reference avoids resending large fitted artifacts through the 4.5 MB public gateway.

Render rejected creation of the requested **free** Python web service with HTTP402: payment information is required at https://dashboard.render.com/billing. No Render service or paid worker/cron resource was created. The Render Docker/Blueprint configuration remains available for a later authorized retry. The current interim Vercel configuration requests no plan, memory or paid build upgrade. Background workers and recurring ingestion must not be represented as active until their actual production checks succeed.

## Verified account export and remaining restore limit

The updated production release streamed a complete 7,921,412-byte encrypted archive and decrypted its 64,697,869-byte payload. All 43 owned typed families and the saved fit/10k/50k/100k simulation inputs, outputs and receipts were retained. See `docs/reports/production-encrypted-backup.json` and the independent cross-deployment persistence report.

Streaming bypasses the platform's non-streamed **response** size cap. The **request** cap remains 4.5 MB: this particular archive cannot be posted to `/api/migrate` as one hosted request. Large web restore needs a future bounded chunked upload or a separate verified recovery path. Typed warehouse/model reconstruction remains partial; do not claim complete project recovery from the successful download/decryption check.

## Server environment

Configure these through the authorized Vercel project environment tools, with sensitive/encrypted values and production/preview targets as appropriate:

```text
DATA_BACKEND=supabase
GRIDIRON_CLOUD_ONLY=1
GRIDIRON_COMPACT_API=1
SUPABASE_URL=<existing gridiron-ai project URL>
SUPABASE_PUBLISHABLE_KEY=<existing publishable key, server-only>
GRIDIRON_ASYNC_SIMULATIONS=1
GRIDIRON_WORKER_REQUEST_LIFETIME=1
SIMULATION_SERVICE_URL=<generated private binding; do not manually configure>
SIMULATION_SERVICE_TOKEN=<retained stable server token shared by web and quant>
APP_URL=<actual stable production HTTPS origin>
DEVICE_TOKEN_ENCRYPTION_KEY=<retained server-only key when needed>
OPENAI_API_KEY=<authorized key if live AI is enabled>
OPENAI_MODEL=<configured model>
```

`GRIDIRON_COMPACT_API` is the deployment-specific transport flag; enable it only with the implemented compact-response/model-reference support. Never prefix provider keys or tokens with `NEXT_PUBLIC_`. Do not configure a Supabase service-role key as the app's user-scoped database client. Preserve the existing simulation token so saved model signatures remain valid across deployments.

The hosted workspace must remain cloud-only: a stale browser cookie must not switch it into an ephemeral SQLite ledger. Existing SQLite files remain preserved on their original server. Import an owned encrypted backup deliberately; do not reset the cloud database.

## Git and production checks

Connect the existing authorized GitHub repository and production branch. Keep `.env*`, `.vercel/`, local data and signing files out of Git. Save the previous production deployment ID before promoting a new release.

After a successful build, verify the returned stable HTTPS URL, `/api/health`, deep dependency health, anonymous account rejection, real Supabase login and owner isolation, exact ledger arithmetic, saved simulation reload, actual 10,000-game workflow and API failure states. Use isolated explicitly generated QA identities only. Physical Safari/Home Screen installation remains a separate user/device verification.

Set the Supabase Auth Site URL and permitted confirmation redirects to the exact production origin using authorized Auth configuration. Do not bypass its redirect allowlist. A functioning existing password session does not establish confirmation email delivery or a correct new-user redirect.

Official references checked: [Services](https://vercel.com/docs/services), [private bindings](https://vercel.com/docs/services/bindings), [configuration](https://vercel.com/docs/services/config-reference), [Python versions](https://vercel.com/docs/functions/runtimes/python/python-version), [Function limits](https://vercel.com/docs/functions/limitations), [function duration](https://vercel.com/docs/functions/configuring-functions/duration), and [project configuration](https://vercel.com/docs/project-configuration/vercel-json).
