# GRIDIRON AI 6.0 delivery and verification

**Application:** https://gridiron-ai-gray.vercel.app  
**Source:** https://github.com/NBDSunsetYT/gridiron-ai  
**Database:** existing Supabase project `qdtdjbapdipopncklsdb`  
**Release status:** Final deployment and production acceptance in progress. This report will be finalized with executed results; it is not a production-completion claim.

## Preserved architecture and records

This is an upgrade to the existing application, not a replacement. Next.js web/API and private Python 3.12/FastAPI compute remain in the existing Vercel Services project. Render previously refused free-service creation with HTTP402 billing verification; no paid service was started and no public Render URL is claimed. Existing Wallet records, owned research, conversations, authentication and PWA features are retained.

The pre-upgrade recovery checkpoint includes a verified Git bundle and an encrypted consistent database snapshot including public tables and selected Auth records. Local decryption and row counts were verified. This is not a claim of complete Auth/Storage reconstruction or verified provider PITR retention. Migrations are additive and existing data was not reset. The fourth small v6 migration increases the bounded application admission pool to 400,000 primary complete games per UTC day without changing hosting plans or resetting existing reservations.

The seven new shared prop tables store research runs, exact contract definitions, observed quotes, model artifacts, immutable prediction snapshots, run results and observed resolutions. Shared writes use a narrow server-only capability; private Wallet, saved combinations, what-if results and conversation history remain authenticated and owner scoped. No research prediction is automatically recorded as a real wager.

## Implemented experience

The mobile navigation is **Home | Games | Props | AI | Wallet**; existing Simulations and advanced controls remain accessible. Home and Props offer **Analyze All Player Props**. The server automatically discovers available contracts, validates exact player identity and thresholds, retrieves current public evidence, reuses or runs coherent 10,000-complete-game simulations, and saves the research snapshot. Progress, source freshness, injury coverage, raw probability, sampling error, parameter uncertainty, calibration status and reasons for withholding valuation are displayed. Cursor pagination pins a snapshot instead of silently changing the result set.

Each simulated player's passing, rushing, receiving and offensive touchdown statistics emerge from shared game plays. Exact integer frequencies support threshold evaluation, with separate whole-game bootstrap samples for parameter sensitivity. Supported private joint research selects 2–12 outcomes from the same simulated games; an independence estimate is labeled separately. Historically supported player-availability what-if scenarios stay explicitly hypothetical. Unsupported injury or weather multipliers are not invented.

The controlled model lab records prospective outcomes, chronological training and separate holdout evaluation, calibration metrics, immutable candidates and operator rollback selection. Unresolved or unavailable participation evidence blocks promotion rather than being counted as a loss or silently dropped. Current raw research is not labeled calibrated without an approved, relevant artifact. Increasing the main sample count reduces sampling error, not underlying uncertainty or market risk.

Wallet accepts event-contract price, quantity and fees separately from American sportsbook odds. Actual stake inclusive of fees and actual settlement payout determine exact cash and P/L. Deposits, withdrawals, transfers and returned stakes are not confused with betting profit. The existing exact-cents ledger and account audit history remain preserved.

The assistant's new private account reports retrieve the authenticated owner's deposits, withdrawals, cash and realized P/L. These deterministic reports work without an OpenAI key, persist in conversation history, and identify `generatedByAI: false`. Source-based public evidence briefs also remain available. General LLM research and specialist tool calling require the missing server-side OpenAI credential; no provider response is fabricated.

## Actual sources and limits

- Published nflverse-compatible schedules, player/team statistics, play-by-play, rosters, snap counts, injury/practice reports and available depth-chart coverage supply football evidence. ESPN venue identity and Open-Meteo forecasts supplement current context. Sources retain timestamps, coverage and hashes. Failed or unverified source refreshes withhold current predictions and do not silently fall back to missing inputs.
- Public **Kalshi** NFL event contracts are an explicitly labeled alternative. Their exact participant identities, rules, thresholds and observed bid/ask prices are retained. They are not relabeled as DraftKings. An observed quote does not guarantee a fill. Missing fee/routing/rounding evidence and non-participation/fair-price exceptions withhold unconditional after-cost value.
- Direct **DraftKings Predictions** and Hard Rock licensed feeds are unavailable in this environment. A validated server-side authorized-feed adapter is implemented; it requires the operator's authorized feed endpoint/token/attestation. Optional verified manual/CSV/OCR workflows remain available but are not described as live data.
- Offensive rushing/receiving touchdowns are modeled. Contracts whose settlement rules also count unsupported defensive or return touchdowns are withheld. Historical-usage probabilities are labeled conditional on the stated participation assumptions; they do not establish unconditional exchange fair value.
- Current complete-game prop forecasts are research-only. Prospective out-of-sample calibration and market advantage are not established. The retained historical benchmark and small retrospective actual-game audit are separately labeled and do not authorize model promotion.
- Confirmed-account email/password authentication works. Apple is disabled and hidden. The existing new-account email-confirmation return URL still requires an operator Auth configuration correction; security and confirmation are not bypassed. See [the previous account audit](AUTH_V5.md).
- Raw upstream data and fitted worker files are cached temporarily; durable summaries and source hashes do not guarantee exact replay of superseded upstream bytes. Private normalized artifact storage remains available through the existing preserved workflow.

## Executed verification

Final local and production test evidence will be recorded here after deployment. Physical iPhone installation is not claimed; browser checks use desktop and iPhone-sized viewports.

## Launch and install

Open **https://gridiron-ai-gray.vercel.app** in Safari on iPhone. Browse games and Props as a guest. Sign in to GRIDIRON AI only for private records. Choose **Share → Add to Home Screen → Add**. The existing manifest, 192px/512px icons, Apple touch icon, standalone mode, safe areas and non-sensitive offline shell remain implemented. Private API responses and authenticated HTML are excluded from service-worker caches.

See [iPhone instructions](IPHONE.md), [developer commands](../README.md), [operator environment](ENV_V6.md), [market provenance](MARKET_DATA_V6.md) and [the model-lab protocol](PLAYER_PROPS_MODEL_LAB.md). Source archives exclude secrets, account databases, QA credentials and signing material. Saving a ZIP to iPhone Files does not execute the hosted web or Python backend. Native IPA/Xcode work remains postponed.
