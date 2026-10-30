# GRIDIRON AI 4.0

Current priority: the installable iPhone PWA at **https://gridiron-ai-gray.vercel.app**. Source is published at [NBDSunsetYT/gridiron-ai](https://github.com/NBDSunsetYT/gridiron-ai). Read the [PWA release status and tests](docs/DELIVERY_PWA.md), [Vercel deployment](docs/VERCEL.md), and [Render status](docs/RENDER.md). Native IPA/Xcode work is postponed.

A functioning NFL research application with an exact-money personal ledger, persistent cloud accounts, evidence-backed market tools, a private Python simulator, and an iPhone web installation path. The Supabase backend is configured and tested against the existing live project. The frontend is deployed to public HTTPS. The same existing Python engine is deployed as a private Vercel Service; production deep health verifies Python and Supabase connectivity. Render rejected free backend creation with HTTP 402 pending account payment verification. Signed-in production checks passed for persistent finances, owner isolation, saved research, and actual 10,000/50,000/100,000-complete-game simulations; see the delivery evidence for their historical-data and uncertainty limits. No signed iPhone IPA is included.

The app uses Next.js 15, React 19, TypeScript, PostgreSQL/Supabase Auth with owner-scoped RLS, and a separate FastAPI modeling service. The original durable SQLite workspace is preserved as an explicit backend option. Missing credentials or source coverage remain visible; no sportsbook odds, injuries, bankroll results, or accuracy figures are fabricated to fill gaps.

## Start locally

Requirements: current Node.js 22+, npm and Python 3.12. Native SQLite builds may also need Python and a C++ compiler. Use the committed lockfile.

```sh
npm ci
cp -n .env.example .env.local
python -m venv .venv
. .venv/bin/activate
pip install -r modeling/requirements.txt httpx
npm run dev:full
```

Preserve an existing `.env.local`; the no-clobber copy above must not replace configured credentials or origins. Open http://localhost:3000. The launcher preserves existing settings/data, creates a private simulation token only when absent, and starts Next plus FastAPI. Its development build uses `.next-local`. Keep the simulation secret stable for signed artifacts. To run the frontend alone, use `npm run dev`; quantitative requests then need a separately configured service.

The environment template is safe for local use: `DATA_DIR=./data`, `APP_URL=http://localhost:3000`. SQLite remains selected until you explicitly choose the cloud workspace in Settings or configure `DATA_BACKEND=supabase`. For cloud use, provide the existing project's server-side `SUPABASE_URL` and `SUPABASE_PUBLISHABLE_KEY`, sign in with Supabase Auth, and follow [cloud setup and migration](docs/SUPABASE.md). Do not initialize another database to work around a migration error.

## What works and what needs configuration

The ledger handles cash movements, wagers, settlement, transfers, refunds, audit history, reconciliation, CSV, and encrypted backups without counting deposits as profit or returned stakes twice. Financial arithmetic uses Decimal and exact cents. Cloud records survive Node restarts and are isolated by database RLS and authenticated financial RPCs. Actual production checks confirmed records survive a Vercel redeployment. A 7.92 MB encrypted export was fully downloaded/decrypted, preserving 64.70 MB of account evidence. That archive exceeds the hosted 4.5 MB upload cap, so large web restore is unavailable; normalized warehouse restoration and provider PITR remain incomplete/unverified. Legacy SQLite records are never silently substituted for a cloud outage.

Earlier local-to-cloud integration fitted 25,303 historical plays and persisted a 10,000-complete-game run with 1,000 game-block bootstrap games. The actual hosted workflow separately passed 10,000/50,000/100,000-complete-game runs using 1,527 real historical plays across 22 games, with verified persistence and separate sampling/parameter uncertainty. These are retrospective research and mechanics checks, not current NFL forecasts or evidence of market advantage. Read the [production evidence](docs/reports/pwa-production-simulation-modes.json).

Market tools support verified manual binary contracts and sportsbook/CSV inputs, immutable quote and prediction history, paper positions separate from real cash, calibrated-model research reports, joint simulation-based parlay analysis, injuries with source/freshness boundaries, and persistent conversations/preferences. Public historical NFL schedules and normalized plays can be imported with provenance. See the [feature matrix](docs/FEATURES.md) for exact scope.

Direct DraftKings Predictions, official live injury/news feeds, licensed sportsbook coverage, OpenAI responses and APNs delivery are **not connected**. Their integration boundaries are documented; they require the corresponding authorized credentials and infrastructure. An APNs token registration is not a delivered notification. Manual source verification is not an independent feed.

The research model suite has 816 chronological held-out home-win outcomes. Its ensemble Brier score is **0.224483**, compared with **0.210157** for indicative historical market probabilities. Lower is better. Market quote timing and settlement compatibility are unverified; the model is **research-only (`productionEligible: false`)**. These results do not establish profitable wagers, player-prop accuracy or validation of the separate play-by-play simulator. Read the [audit](docs/AUDIT_V4.md) and [full report](docs/reports/v4-model-benchmark.json).

## Verify, build and package

```sh
npm test
npm run test:python
npm run test:postgres
npm run typecheck
npm run build
npx playwright install chromium
npm run test:e2e
npm run package
```

The cloud-job release passed 259 TypeScript tests, 60 Python tests, nine Node workflow checks, 28 desktop/iPhone Chromium checks, and a production Next.js build. A subsequent four-check hosting compatibility suite and type check passed after the provider required Node middleware. PostgreSQL migration and live RLS checks are recorded separately. These behavior/mechanics checks do not establish historical model accuracy. Current production evidence and remaining limits are recorded in [DELIVERY_PWA.md](docs/DELIVERY_PWA.md); earlier release evidence remains in [DELIVERY_V4.md](docs/DELIVERY_V4.md). Commands above are instructions, not proof that an arbitrary deployment passes. The versioned source package is `artifacts/gridiron-ai-v4-source.zip` with matching `artifacts/gridiron-ai-v4-source.sha256`; use the actual generated files linked in the final delivery. Archives exclude credentials, runtime databases and private records.

## Deploy and install

- [Hosted deployment](docs/DEPLOYMENT.md) and [private Python service](docs/QUANT_SERVICE.md)
- [Supabase Auth, RLS, migration and recovery](docs/SUPABASE.md); [schema](docs/SUPABASE_SCHEMA.md)
- [SQLite upgrade and recovery](docs/MIGRATIONS.md); [security](docs/SECURITY.md)
- [iPhone PWA and saving ZIPs to Files](docs/IPHONE.md)
- [Native iPhone source, Xcode and private installation](docs/NATIVE_IPHONE.md)
- [NFL data preparation](docs/NFLVERSE.md); [scheduling](docs/DATA_PIPELINE.md); [typed play warehouse](docs/WAREHOUSE_PBP.md)
- [Simulation](docs/SIMULATION.md); [models](docs/MODELS.md); [4.0 audit](docs/AUDIT_V4.md)

The native source is a real Capacitor/Swift Xcode project; project generation and synchronization were tested. Linux cannot compile/sign it with Apple's SDK. A Mac, Xcode, Apple signing/provisioning, your physical iPhone and an actual HTTPS backend are required. App Store and TestFlight publication are not configured. Downloading source to iPhone Files does not execute Next.js, PostgreSQL or Python.

Provider keys, simulation tokens, APNs signing credentials, database passwords and administrative Supabase keys belong only in trusted server configuration. Never expose them through `NEXT_PUBLIC_*` or bundle them with the native app. The project does not place wagers or promise guaranteed results.

The prior [2.0 README](docs/README_V2.md), [delivery report](docs/DELIVERY_REPORT.md), and [upgrade audit](docs/UPGRADE_AUDIT.md) are retained as historical records; use the 4.0 documents for current capabilities.
