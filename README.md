Version 14.0: [original GAFIE candidate, Simulation vs. Reality, automatic evaluation, storage and remaining validation limits](docs/GAFIE_GALL_14.md).

**Engine overhaul / NBA research:** see [the v15 audit and release report](docs/ENGINE_V15_REPORT.md). The 500-game football audit did not justify promoting the replacement football candidate. NBA is a separate experimental possession/rotation engine; raw probabilities are explicitly uncalibrated. Existing user records and infrastructure are preserved.


Version 12.1: [automatic probabilities, sorting, market comparison and limitations](docs/PROPS_V12_1.md).

Version 12 automatic prop research: [operation, limitations and recovery](docs/AUTOMATIC_PROPS_V12.md).

# Probability engine repair — 11.0.1

See [the observed cause, repair and verification scope](docs/PROBABILITY_REPAIR.md). Probability requests now follow backend jobs, preserve specific failures and reopen compact simulations from durable references. Existing data and infrastructure are preserved.

# GRIDIRON AI 11.0 — compact cloud storage

The existing application is preserved. See [storage architecture, retention, recovery and provider activation](docs/GRIDIRON_V11.md). Supabase remains the private account and ledger authority. MongoDB/R2 integrations are opt-in and are not reported as connected until actual authorized checks pass.

# GRIDIRON AI 10.2

Existing-app upgrade and shared research storage repair: [architecture, operational scope and recovery](docs/GRIDIRON_V10_2.md). Production remains **https://gridiron-ai-gray.vercel.app**. The previous10.0 report below is retained as historical evidence.

# GRIDIRON AI10.0

Existing-app upgrade: [operational scope, recovery and remaining requirements](docs/GRIDIRON_V10.md).

# GRIDIRON AI 9.0.0

GRIDIRON AI is an installable NFL and College Football research app with public game analysis and a private personal wallet. The existing application has been upgraded; its previous ledger, research tools and data remain preserved.

Version9.0 connects the PropLine Hobby NFL/CFB sportsbook feed through a Render-only secret gateway. See [PropLine9.0 verification and limits](docs/PROPLINE_V9.md). Earlier8.0 evidence below remains historical.

The app is hosted at **https://gridiron-ai-gray.vercel.app**. Version 8 adds a shared NFL / College Football selector, a separate NCAA complete-game historical-baseline simulator, independent player distributions, sport-scoped saved research and Wallet filters. Existing NFL simulation code, private records and the PWA are preserved.

The deployed public workflow passed 48 scoped checks: 15 API, 18 real desktop/iPhone-sized Chromium/WebKit browser checks and 15 PWA checks. A real hosted 10,000-game college result reopened on fresh requests and reloads. Full acceptance remains partial. [DELIVERY_V8.md](docs/DELIVERY_V8.md) records actual evidence and remaining limits; [7.0 delivery](docs/DELIVERY_V7.md) remains retained. Tagged source releases require successful verification on their exact commit.

**8.0 historical external limits (superseded for PropLine/Render by9.0):** no authorized DraftKings Predictions event-contract feed is configured. New public persisted research is paused at the existing database reserve. The Render-only BALLDONTLIE/CollegeFootballData gateway is implemented and tested, but one explicitly free service creation returned HTTP 402 requiring owner payment-information authorization. No Render service, provider authentication or account subscription tier has been verified. No API key was moved to Vercel and no paid resource or trial was activated. Existing saved history and private Wallet remain available.

The DraftKings repair distinguishes missing configuration, credential rejection, empty verified feeds, rate limits, outages and unsupported mapping/rules. Zero verified accessible contracts does not mean the platform has no NFL markets. BALLDONTLIE DraftKings sportsbook reference odds remain separate from DraftKings Predictions percentage contracts. See [DraftKings access](docs/DRAFTKINGS_ACCESS.md) and [8.0 source boundaries](docs/DELIVERY_V8.md).

## Open the app

1. Open GRIDIRON AI and choose NFL or College Football. Available published games and public research do not require an app or database-provider login.
2. Tap a game. The app retrieves available statistics, reported injuries and weather, then reuses or queues a 10,000-complete-game analysis.
3. For NFL player props, choose **Sportsbook references (PropLine)** or **DraftKings Predictions contracts** explicitly. **ANALYZE ALL NFL PLAYER PROPS** checks authorized sportsbook reference access for the selected verified matchup; it does not claim full-slate coverage or convert those odds into percentage-priced contracts. The separate **Analyze All NFL Markets** event-contract workflow validates exact identities, thresholds, quotes and settlement rules and reports missing licensed access honestly. In College Football, **Analyze Game** produces a separate complete-game historical baseline; independent player distributions remain separate from missing market contracts.
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

Performance release: [12.1.1 implementation, measured benchmarks and recovery](docs/PERFORMANCE_12_1_1.md).


## Football research desk — 12.2

The existing Props screen now includes a compact research board, followed selections, source-backed chronological trends and exact sportsbook comparisons. Model probabilities, observed historical frequencies and market benchmarks retain distinct labels. See [implementation and limitations](docs/RESEARCH_DESK_12_2.md) and [live acceptance](docs/reports/research-desk-release.json). No prediction method, simulation count or financial record was changed.

### Controlled iterative model research

The local NFL/CFB/NBA learner completed three challenger rounds across 112 real games and352 graded forecasts (3.52 million complete simulated games). All leagues stopped at the validation plateau. No challenger satisfied every reliability gate, so production forecasting defaults remain unchanged. See [the measured results](docs/ITERATIVE_LEARNING_RESULTS.md), [protocol and recovery instructions](docs/ITERATIVE_LEARNING.md), and Model validation in the app (`/#engine`). The study is retrospective; complete original pregame injury/lineup/publication archives are unavailable.

Hosting status, 2026-11-04: the 15.1.0 build was deployed and passed production checks, then fresh requests returned Vercel HTTP 402 `DEPLOYMENT_DISABLED`. The resume API did not clear the platform block. No plan/billing change was made. See [release verification](docs/reports/v16-release-verification.json) before treating the cloud URL as currently available.
