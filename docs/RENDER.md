# Render compute deployment

This configuration preserves the existing Python/FastAPI engine and reuses Supabase project `qdtdjbapdipopncklsdb`. The web app stays on Vercel. No duplicate database, paid background worker, or paid Render cron job is defined.

`render.yaml` is a Blueprint for a **free** Docker web service using `deployment/render/Dockerfile`. The startup wrapper accepts Render's dynamic `PORT`, starts one Uvicorn process as an unprivileged user, and limits native BLAS thread pools to one thread. `/health` is the health-check path; all fit/simulation/model endpoints require the stable server bearer token. CORS is not opened because only the Vercel server calls compute.

Set the existing `SIMULATION_SERVICE_TOKEN` through Render's environment-variable controls and set exactly the same value in Vercel. Preserve it across deploys: artifact signatures and saved-result receipts depend on continuity. Never put it in Git, public JavaScript, query strings or screenshots. `SUPABASE_URL` and `SUPABASE_PUBLISHABLE_KEY` support owner-scoped queue requests; never use a service-role key in ordinary client operations.

Native connector creation has fewer configuration options than the Blueprint. If deployed through that connector, verify whether `/health` was selected explicitly; otherwise Render's default TCP health probe is the configured liveness check. An external successful GET `/health` separately verifies HTTP readiness. Do not claim a Blueprint setting was applied merely because this file exists.

## Free-plan boundaries

Current Render docs specify 0.1 CPU and 512 MB RAM, with 750 free instance hours per workspace/month and idle spin-down after 15 minutes. Cold starts can delay the first request. Free services are a capacity-constrained personal deployment, not an always-on production SLA. No periodic request is added solely to defeat idle spin-down.

Synchronous 100,000-game research requests can exceed the Vercel/Next request deadline on 0.1 CPU. Durable background execution and polling must be used for such jobs; an in-memory queue alone is not restart-safe. The Supabase queue must preserve every input, status, immutable result and owner boundary. Report any remaining async-worker limitations rather than calling an accepted job completed.

Use GitHub Actions or another already-authorized no-cost scheduler for genuine source updates when configured. Do not create paid Render worker/cron service types without a price review and explicit authorization. An unavailable official injury feed must remain unavailable; scheduled execution cannot invent injury facts.

## Account inspection

The connected account exposed one workspace and no services at initial inspection. The workspace is `tea-dbidrq6c6qcc73a7n0u0`; no service has been created by preparing this source. The actual deployed service URL, deploy ID, plan, logs and HTTP checks must be recorded after the source repository is reachable and the native service creation succeeds.

## Local validation

```sh
python -m unittest deployment/render/test_runtime.py
```

The two startup tests cover valid dynamic/default ports, stable-token requirements and native-thread bounds. They do not establish a remote deployment, an NFL backtest or a signed-in application workflow.
