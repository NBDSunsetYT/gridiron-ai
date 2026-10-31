# GRIDIRON AI 7.0

GRIDIRON AI is an installable NFL research app with public game analysis and a private personal wallet. The existing application has been upgraded; its previous ledger, research tools and data remain preserved.

The existing application is hosted at **https://gridiron-ai-gray.vercel.app**. Version 7 makes DraftKings Predictions the explicit primary event-contract reference and adds an all-NFL market research workflow alongside the existing player-prop scanner. Exact threshold distributions, immutable snapshots, controlled calibration, private joint simulations and event-contract Wallet records are preserved. Executed release checks and remaining limitations are recorded in [DELIVERY_V7.md](docs/DELIVERY_V7.md); earlier evidence remains in [DELIVERY_V6.md](docs/DELIVERY_V6.md) and [DELIVERY_V5.md](docs/DELIVERY_V5.md).

## Open the app

1. Open GRIDIRON AI. Published NFL games and shared research are available as a guest.
2. Tap a game. The app retrieves available statistics, reported injuries and weather, then reuses or queues a 10,000-complete-game analysis.
3. Tap **Analyze All NFL Markets** for game and player event-contract research, or **Analyze Player Props** for the player-only workflow. The backend validates the selected authorized source, exact identities, thresholds and settlement rules, reuses or queues complete-game simulations, and preserves prior snapshots. If direct DraftKings access is not configured, that workflow reports it as unavailable. An explicitly selected alternative keeps its own provider identity. Use **Analyze Game** for one matchup.
4. Sign in to **GRIDIRON AI** when opening Wallet or saving personal research and conversation history. An application account is not a Supabase developer account.
5. On iPhone, open the app in Safari and choose **Share → Add to Home Screen → Add**.

Primary navigation is **Home | NFL | Props | AI | Wallet**. Simulations, existing contract imports, detailed modeling controls, provider status and administrative tools remain available through optional Advanced Mode. Normal public research does not require a CSV upload, manually entered statistics, API configuration or a database dashboard.

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

These are reproducible commands, not a claim that any arbitrary deployment passes. See [7.0 verification](docs/DELIVERY_V7.md) for actual executed checks and provider state. Source archives exclude credentials, financial databases, runtime caches and signing material.

- [DraftKings Predictions access and standard fee reference](docs/reports/v7-draftkings-access-audit.json)
- [Player-prop sources and contract verification](docs/MARKET_DATA_V6.md)
- [Controlled model development and rollback](docs/PLAYER_PROPS_MODEL_LAB.md)
- [Operator configuration](docs/ENV_V7.md)
- [Deploying the existing Vercel services](docs/VERCEL.md)
- [Supabase storage, security and recovery](docs/SUPABASE.md)
- [GRIDIRON app authentication](docs/AUTH_V5.md)
- [iPhone installation and saving source to Files](docs/IPHONE.md)
- [Original data upgrade and recovery](docs/MIGRATIONS.md)
- [Historical model audit](docs/AUDIT_V4.md)
- [Earlier PWA delivery and limitations](docs/DELIVERY_PWA.md)

Native IPA/Xcode work remains postponed. Saving source files to iPhone Files does not execute the web or Python backend. The project never requests sportsbook passwords or places real wagers.
