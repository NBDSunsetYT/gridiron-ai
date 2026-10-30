# Private quantitative service

The Node application proxies authenticated requests to a separate private Python FastAPI service. Fitted artifacts, simulation results and complete replay inputs persist in the signed-in owner's **selected backend**: Supabase PostgreSQL/RLS in cloud mode, or the preserved SQLite workspace in legacy mode. The Python service is stateless: requests carry signed artifacts and the stable server secret verifies them. No shared model-directory volume is required. Keep the configured Supabase project/account and stable secrets across cloud redeployments; retain the same persistent DATA_DIR for legacy records. See [DEPLOYMENT.md](DEPLOYMENT.md) and [SUPABASE.md](SUPABASE.md) before changing backend selection. Real evidence is required; synthetic mechanical-test fixtures are not substituted in production.

## Local

The simplest two-service setup is `npm run dev:full` after installing the Python requirements. It loads existing `.env.local`, creates a stable local simulation token only if absent, and preserves data. The manual process-manager setup below remains supported.

```sh
python -m venv .venv
. .venv/bin/activate
pip install -r modeling/requirements.txt
uvicorn modeling.service:app --host 127.0.0.1 --port 8000 --workers 1
```

Set `SIMULATION_SERVICE_TOKEN` to the same random value of at least32 characters in the Python process and the Next server. Set the Next server's `SIMULATION_SERVICE_URL=http://127.0.0.1:8000`. `.env.local` is loaded by Next, not automatically by Python; inject the Python environment through your trusted process manager. Keep tokens out of commands, source and logs. Changing the token invalidates signatures on existing artifacts, so retain controlled key continuity or refit the original evidence.

## Docker Compose

Compose starts `app` and private `quant` services. `app` calls `http://quant:8000`; only app port3000 is bound to host loopback. Set `APP_URL` to your public HTTPS origin and set `SIMULATION_SERVICE_TOKEN` in untracked `.env` before `docker compose up -d --build`. Empty token configuration returns an explicit unavailable response. The service does not provide a public docs endpoint and checks bearer authorization on fit/simulate. Health status indicates configuration, not a validated trained model. Do not expose port8000 directly.

The service permits one fit/simulation concurrently and returns429 when busy. It bounds request bytes and simulation count. The Next proxy has a240-second upstream timeout; deploy to a Node runtime/proxy that permits that duration. Jobs preserve failure state. Large historical datasets may need an offline preparation pipeline and additional capacity rather than an increased web request limit.

## Injury jobs and recovery

The CRON_SECRET recovery command below applies to the **legacy SQLite workspace**. Supabase jobs require the authenticated owner and can be advanced through the owned research pipeline or signed-in controls; a global cron secret does not identify a cloud user. See [DEPLOYMENT.md](DEPLOYMENT.md) for the private owner-session scheduler.

Injury changes only invalidate simulations that explicitly reference the affected entity. Replays use the original stored signed inputs and supported historical scenario cohorts. No generic injury probability multiplier is applied. Single-player empirical scenarios require adequate documented evidence; unsupported joint scenarios or stale evidence remain blocked.

Next after() attempts dispatch, but a durable operator cron is required for retries/process interruption. Configure a separate random `CRON_SECRET` of at least32 characters and the HTTPS `APP_URL` in a trusted scheduler's environment, then run:

```sh
node scripts/run-jobs.mjs
```

This calls the protected job endpoint; never put the secret in arguments or a public URL. The worker recovers abandoned leases after20 minutes. The scheduler, its environment, monitoring and retention are operator responsibilities. Do not claim continuous background ingestion merely because the worker script exists.
