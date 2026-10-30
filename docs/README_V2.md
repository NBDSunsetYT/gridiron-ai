# GRIDIRON AI 2.0

A mobile-first NFL research workspace with a real personal ledger, manual and authorized-feed market ingestion, transparent probability calculations, and an optional OpenAI research assistant. Empty or unconfigured sources are shown explicitly. There are no seeded sportsbook prices, injuries, performance records, or financial results in production.

The implementation uses Next.js 15, React 19, TypeScript, Recharts, Framer Motion, and a durable SQLite database. SQLite is a deliberate single-instance deployment choice: it provides atomic transactions and an auditable ledger without requiring a paid database account. It is **not** safe to deploy this version to a stateless/serverless host without a persistent-volume database adapter.

## Run locally

Requirements: Node.js 22 or later, npm, and a C++ compiler/Python if a prebuilt `better-sqlite3` binary is unavailable. Use a current supported Node release.

```sh
npm ci
cp .env.example .env.local
npm run dev
```

Open http://localhost:3000 and create an account. The local database is created in `./data` unless `DATA_DIR` is set. The environment template uses local-safe defaults (`DATA_DIR=./data`, `APP_URL=http://localhost:3000`); Docker overrides the data path. Set the actual HTTPS origin for production. Money is stored as integer cents and calculated with Decimal arithmetic. Your records start empty.

To run the Python simulator too, use Python 3.12 and launch both services:

```sh
python -m venv .venv
. .venv/bin/activate
pip install -r modeling/requirements.txt httpx
npm run dev:full
```

The launcher creates a private random simulation token in ignored `.env.local` only when absent, preserves existing settings and data, and launches FastAPI on `127.0.0.1:8000` plus Next on port 3000. Its development build uses `.next-local`. Keep the token stable for signed model artifacts. No paid API key is needed for local simulation. Real historical inputs are required: see [data preparation](docs/NFLVERSE.md). OpenAI and licensed odds feeds remain credential dependent.

```sh
npm test
npm run test:python
npm run build
npm run start
npx playwright install chromium
npm run test:e2e
node scripts/package.mjs
```

The ZIP is created at `artifacts/gridiron-ai-source.zip`. Dependency installation needs network access. Browser tests need a browser runtime. Read the final delivery report for checks actually performed in the authoring environment; commands in this README are instructions, not claims that every environment has been tested.

## Credentials

All provider requests run on the server. Never put credentials in `NEXT_PUBLIC_*`, source control, the hosting manifest, browser storage, screenshots, or CSV files.

| Variable | Purpose |
| --- | --- |
| `DATA_DIR` | Writable persistent directory for SQLite. |
| `APP_URL` | Canonical HTTPS origin for the deployment. |
| `ODDS_API_KEY` | Optional The Odds API credential. Provider entitlement determines the actual available markets/books. |
| `OPENAI_API_KEY` | Optional OpenAI API credential for GRIDIRON INTELLIGENCE. |
| `OPENAI_MODEL` | Assistant model; default is documented in `.env.example`. |
| `CRON_SECRET` | Optional server secret for an unattended ingest job if configured. |

DraftKings and Hard Rock are only shown as actual feed prices when a configured authorized provider returns them. A provider key does not establish entitlement to every sportsbook or jurisdiction. Manual prices remain labeled manual. OCR, restricted private API scraping, and geolocation bypasses are not implemented.

## Guides

- [Deployment and operations](docs/DEPLOYMENT.md)
- [iPhone installation and ZIP downloads](docs/IPHONE.md)
- [Capabilities and limitations](docs/FEATURES.md)
- [Modeling and evidence](docs/MODELS.md)
- [Security and privacy](docs/SECURITY.md)
- [Release verification](docs/DELIVERY_REPORT.md)
- [Upgrade inventory](docs/UPGRADE_AUDIT.md)
- [Database continuity and recovery](docs/MIGRATIONS.md)
- [Private quantitative service](docs/QUANT_SERVICE.md)
- [Complete-game simulation](docs/SIMULATION.md)
- [Safe upgrades and migration recovery](docs/MIGRATIONS.md)
- [2.0 upgrade audit](docs/UPGRADE_AUDIT.md)
- [Quantitative service deployment](docs/QUANT_SERVICE.md)

## Data and model policy

A calculated probability is only as useful as the supplied data and modeling assumptions. Historical hit frequency, a fitted distribution probability, a calibrated out-of-sample probability, model accuracy, and expected value are different quantities. This application keeps them distinct and does not create evidence when inputs are missing. Correlated parlays require joint evidence or an explicit correlation model. Independence estimates are labeled separately.

No selection or parlay is guaranteed. This is research and personal recordkeeping software, not a sportsbook, automated wagering service, or verified profitable trading system. The application does not place bets.

## 2.0 research additions

The research desk includes manually verified YES/NO contracts, immutable quote/forecast/settlement history, a paper portfolio kept separate from cash accounting, source-attributed injuries, odds movement and closing-price comparison, prospective calibration records, and a private Python simulation service. Models must be fitted from real chronological play-by-play data; there is no bundled trained production model. Scenario simulations preserve joint outcomes from the same run and quote combined prices explicitly.

A real retrospective public nflverse holdout audit is included in `docs/reports/baseline-backtest.json`: 272 2024 games with a fixed 45.5 total threshold, expanding historical fit, and 2023 initialization. Its Brier score is approximately **0.25564, worse than the 0.25 constant-50% baseline**. The baseline is not promoted. This is a retrospective diagnostic, not validation of the play-by-play simulator or a record of executable market trades. See the report and [model guide](docs/MODELS.md).
