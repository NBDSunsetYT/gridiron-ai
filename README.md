# GRIDIRON AI 8.0.0

GRIDIRON AI is an installable NFL and College Football research app with public game analysis and a private personal wallet. The existing application has been upgraded; its previous ledger, research tools and data remain preserved.

The existing application is hosted at **https://gridiron-ai-gray.vercel.app**. Version 8 adds a shared NFL / College Football selector, a separate NCAA complete-game historical-baseline simulator, independent player distributions, sport-scoped saved research and Wallet filters. NFL simulation and fitting code, private records and the existing PWA are preserved. 8.0 is deployed and all 15 actual public API checks passed, including a real hosted 10,000-game college simulation; full acceptance remains partial. Signed public-only ephemeral caching now reopens a verified result on fresh requests; 15 PWA checks passed, and the first 18-browser-check execution passed before a later workspace transport failure; fresh hosted-runner browser evidence and exact final source-release CI remain pending; [DELIVERY_V8.md](docs/DELIVERY_V8.md) records executed checks and exact limitations. Earlier [7.0 delivery](docs/DELIVERY_V7.md) remains retained.

**Current external limits:** no authorized DraftKings Predictions event-contract feed is configured. New public persisted research is paused at the existing database reserve. The Render-only BALLDONTLIE/CollegeFootballData gateway is implemented and tested, but one explicitly free service creation returned HTTP 402 requiring owner payment-information authorization. No Render service, provider authentication or account subscription tier has been verified. No API key was moved to Vercel and no paid resource or trial was activated. Existing saved history and private Wallet remain available.

The DraftKings repair distinguishes missing configuration, credential rejection, empty verified feeds, rate limits, outages and unsupported mapping/rules. Zero verified accessible contracts does not mean the platform has no NFL markets. BALLDONTLIE DraftKings sportsbook reference odds remain separate from DraftKings Predictions percentage contracts. See [DraftKings access](docs/DRAFTKINGS_ACCESS.md) and [8.0 source boundaries](docs/DELIVERY_V8.md).

## Open the app

1. Open GRIDIRON AI and choose NFL or College Football. Available published games and public research do not require an app or database-provider login.
2. Tap a game. The app retrieves available statistics, reported injuries and weather, then reuses or queues a 10,000-complete-game analysis.
3. For NFL player props, choose **Sportsbook references (BALLDONTLIE)** or **DraftKings Predictions contracts** explicitly. **ANALYZE ALL NFL PLAYER PROPS** checks authorized sportsbook reference access for the selected verified matchup; it does not claim full-slate coverage or convert those odds into percentage-priced contracts. The separate **Analyze All NFL Markets** event-contract workflow validates exact identities, thresholds, quotes and settlement rules and reports missing licensed access honestly. In College Football, **Analyze Game** produces a separate complete-game historical baseline; independent player distributions remain separate from missing market contracts.
4. Sign in to **GRIDIRON AI** when opening Wallet or saving personal research and conversation history. An application account is not a Supabase developer account.
5. On iPhone, open the app in Safari and choose **Share → Add to Home Screen → Add**.

Primary navigation is **Home | NFL / College | Props | AI | Wallet**, with a shared sport selector. Simulations, existing contract imports, detailed modeling controls, provider status and administrative tools remain available through optional Advanced Mode. Normal public research does not require a CSV upload, manually entered statistics, API configuration or a database dashboard.

## Evidence and privacy

Published NFL information and shared analyses use separate database tables from personal records. Guests can read public research. Shared writes require a server-only capability; they cannot be performed by public database clients. Existing private tables retain authenticated ownership checks and row-level security.

The personal ledger supports deposits, withdrawals, wagers, settlements, transfers, refunds, adjustments, reconciliation, CSV and encrypted exports using exact cents/Decimal arithmetic. Deposits are not profit and returned stakes are not counted twice. The original SQLite workspace is preserved; moving an existing local account to the cloud still requires its owned encrypted-import procedure. No automatic reassignment of private records is performed.

Automatic research uses published nflverse-compatible records, source timestamps and actual complete-game simulations. Player statistics emerge from shared plays. Unsupported availability assumptions are withheld rather than replaced with arbitrary injury multipliers. A reported injury is not automatically an official confirmed inactive. Automatic team win estimates remain an incompletely injury-adjusted historical baseline; numerical weather effects and calibrated active/limited/inactive mixture weights are not applied. Missing practice, snap, depth-chart or market coverage remains explicit.

Live DraftKings Predictions contract access requires an authorized source. Traditional sportsbook odds are not silently substituted for binary contracts with different fees or settlement terms. Verified manual/CSV/OCR imports remain optional advanced fallbacks. Verified public Kalshi event-contract quotes are separately labeled, without claiming equivalence to DraftKings contracts or calculating fee-dependent value when fees are unknown. No market prices are invented.

Source-based research briefs work without a language-model provider and are identified as evidence briefs. Exact signed-in withdrawal, deposit, balance and realized P/L questions also work through deterministic database reports, labeled as calculated reports rather than AI generation. Live OpenAI conversation and Apple sign-in operate only when their server-side providers are configured; both are currently unavailable. Confirmed-account password sign-in passed production tests. New-account email confirmation still needs an operator correction to the provider’s production return-URL allowlist; see [the account audit](docs/AUTH_V5.md).

The research models remain **research-only**. A separate retained 816-outcome chronological ensemble audit has Brier **0.224483** versus indicative historical market **0.210157**; lower is better. That result does not validate the new automatic play-by-play forecasts, whose out-of-sample calibration remains unverified. Source availability and market timing limits remain documented. More simulations reduce Monte Carlo sampling noise, not underlying model uncertainty, and do not establish market advantage or guaranteed results.

## Developer launch

End users use the hosted app. For development, use Node.js 22+, Python 3.12 and the committed lockfile:

```sh
npm ci
cp -n .env.example .env.local
python -m venv .venv
. .venv/bin/activate
pip install -r modeling/requirements.txt httpx
npm run dev:full
```

Preserve an existing `.env.local`. Backend credentials and ingestion capabilities belong only in server configuration. Use the existing Supabase project `qdtdjbapdipopncklsdb`; do not create a replacement or reset its database. Development may explicitly select the preserved legacy SQLite workspace. The hosted deployment pins private records to persistent PostgreSQL.

## Verification and delivery

```sh
npm test
node --test scripts/simulation-workflow.test.mjs
npm run test:python
npm run test:postgres
npm run typecheck
npm run build
npx playwright install chromium
npm run test:e2e
npm run package
```

These are reproducible commands, not a claim that any arbitrary deployment passes. See [8.0 verification](docs/DELIVERY_V8.md) for actual executed checks, pending production acceptance and provider state. Source archives exclude credentials, financial databases, runtime caches and signing material.

- [DraftKings Predictions access and standard fee reference](docs/reports/v7-draftkings-access-audit.json)
- [Player-prop sources and contract verification](docs/MARKET_DATA_V6.md)
- [Controlled model development and rollback](docs/PLAYER_PROPS_MODEL_LAB.md)
- [8.0 deployment, provider boundaries and remaining owner actions](docs/DELIVERY_V8.md)
- [Preserved operator configuration](docs/ENV_V7.md)
- [Deploying the existing Vercel services](docs/VERCEL.md)
- [Supabase storage, security and recovery](docs/SUPABASE.md)
- [GRIDIRON app authentication](docs/AUTH_V5.md)
- [iPhone installation and saving source to Files](docs/IPHONE.md)
- [Original data upgrade and recovery](docs/MIGRATIONS.md)
- [Historical model audit](docs/AUDIT_V4.md)
- [Earlier PWA delivery and limitations](docs/DELIVERY_PWA.md)

Native IPA/Xcode work remains postponed. Saving source files to iPhone Files does not execute the web or Python backend. The project never requests sportsbook passwords or places real wagers.
