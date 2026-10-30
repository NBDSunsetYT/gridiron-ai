# Render compute deployment

This configuration preserves the existing Python/FastAPI engine and reuses Supabase project `qdtdjbapdipopncklsdb`. The web app stays on Vercel. No duplicate database, paid background worker, or paid Render cron job is defined.

`render.yaml` is a Blueprint for a **free** Docker web service using `deployment/render/Dockerfile`. The startup wrapper accepts Render's dynamic `PORT`, starts one Uvicorn process as an unprivileged user, and limits native BLAS thread pools to one thread. `/health` is the health-check path; all fit/simulation/model endpoints require the stable server bearer token. CORS is not opened because only the Vercel server calls compute.

Set the existing `SIMULATION_SERVICE_TOKEN` through Render's environment-variable controls and set exactly the same value in Vercel. Preserve it across deploys: artifact signatures and saved-result receipts depend on continuity. Never put it in Git, public JavaScript, query strings or screenshots. `SUPABASE_URL` and `SUPABASE_PUBLISHABLE_KEY` support owner-scoped queue requests; never use a service-role key in ordinary client operations.

Native connector creation has fewer configuration options than the Blueprint. If deployed through that connector, verify whether `/health` was selected explicitly; otherwise Render's default TCP health probe is the configured liveness check. An external successful GET `/health` separately verifies HTTP readiness. Do not claim a Blueprint setting was applied merely because this file exists.

## Free-plan boundaries

Current Render docs specify 0.1 CPU and 512 MB RAM, with 750 free instance hours per workspace/month and idle spin-down after 15 minutes. Cold starts can delay the first request. Free services are a capacity-constrained personal deployment, not an always-on production SLA. No periodic request is added solely to defeat idle spin-down.

Synchronous 100,000-game research requests can exceed the Vercel/Next request deadline on 0.1 CPU. The implemented `POST /jobs` endpoint accepts an already-saved owner-scoped Supabase job, verifies the current owner JWT, claims it conditionally, and executes it in a background thread. Inputs/status/results remain in Supabase; memory is only an execution reservation. One job runs at a time. Heartbeats retain the active lease, and completion/failure updates require that same lease. The worker writes a version2 numeric-canonical HMAC receipt; the web server verifies it before displaying generated outputs.

Owner access tokens are held only in memory and never persisted or logged. Expired credentials never fall back to an administrative key. A verified owner reconnects to reconcile/resume an expired or interrupted job. Graceful shutdown returns active work to queued where possible; an interrupted process still leaves durable inputs and a recoverable lease. Closing the browser does not cancel already accepted compute, but redispatch after a crash/redeploy or behind another active job can require the owner to reopen the application. No accepted/queued acknowledgement is described as completed work.

Use GitHub Actions or another already-authorized no-cost scheduler for genuine source updates when configured. Do not create paid Render worker/cron service types without a price review and explicit authorization. An unavailable official injury feed must remain unavailable; scheduled execution cannot invent injury facts.

## Account inspection

The connected account exposed one workspace and no services at initial inspection. The workspace is `tea-dbidrq6c6qcc73a7n0u0`; no service has been created by preparing this source. The actual deployed service URL, deploy ID, plan, logs and HTTP checks must be recorded after the source repository is reachable and the native service creation succeeds.

## Local validation

```sh
python -m unittest deployment/render/test_runtime.py
```

The two startup tests cover valid dynamic/default ports, stable-token requirements and native-thread bounds. They do not establish a remote deployment, an NFL backtest or a signed-in application workflow.

## Executed container checks

The Render-specific Docker image built successfully and ran as UID 1001 on a dynamic port. Its actual HTTP health endpoint returned ready, anonymous compute returned 401, and the runtime contained no local environment file, user database or build CA. Source copies explicitly retain the runtime owner so restrictive source permissions do not break startup. See `deployment/render/verification.json`. These checks ran locally and do not establish a remote Render URL or deployment.

The async worker has 14 additional regression tests; the combined worker and existing HTTP service suite passed 20 tests. They cover an independently generated Node/Python receipt vector, real fixture compute, RLS-scoped reads/claims, duplicate prevention, expired-token recovery, lease replacement, shutdown, safe errors and bounded gzip recovery. These fixture tests do not establish NFL calibration or a remote Render deployment.

## Actual remote creation result

After GitHub main became reachable, an authorized native creation was attempted with the explicit `free` plan. Render rejected it with HTTP **402**: “Payment information is required to complete this request.” The follow-up service list confirmed no resource was created, and no Render backend URL exists. No paid plan, worker, cron service or database was provisioned. The account owner must complete billing verification at https://dashboard.render.com/billing before another free-service attempt. Do not send card details through chat or bypass this platform requirement.

The same existing FastAPI application can run as a private Vercel service while Render remains blocked. Set `GRIDIRON_WORKER_REQUEST_LIFETIME=1` for serverless execution: `/jobs` then keeps its request alive through compute and result persistence, instead of returning with an untracked daemon thread. The web tier uses its supported after-response lifecycle to keep that private invocation alive while the browser polls durable Supabase state. Render’s normal persistent-process mode continues to use background threads.
