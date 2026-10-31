# GRIDIRON AI 7.0 delivery and verification

**Application:** https://gridiron-ai-gray.vercel.app  
**Source:** https://github.com/NBDSunsetYT/gridiron-ai  
**Database:** existing Supabase project `qdtdjbapdipopncklsdb`  
**Status:** Implementation and verification in progress. This draft is not a deployment or completed-acceptance claim.

## Preserved application

This release upgrades the existing Next.js application, private Python/FastAPI compute and persistent Supabase database. The previous app, ledger, conversations, immutable predictions, player-prop research, model lab, optional advanced tools and iPhone PWA are preserved. Native IPA/Xcode work remains postponed.

The operational Python engine is privately bound to the existing Vercel Services deployment. A Render backend was not previously created: the account returned HTTP402 pending billing verification. No paid resources are being provisioned. Vercel's Git integration and ChatGPT's GitHub connector are separate authorizations; a prepared GitHub workflow does not prove provider-native automatic deployment is connected.

A source recovery checkpoint preserves the prior Git history and complete 4.7MB v6 archive. Nineteen managed database migrations are aligned to their actual native versions and SQL hashes. The bounded app admission pool is 500,000 primary complete games per UTC day; existing usage reservations are preserved. This changes neither a provider plan nor a hosting quota and starts no paid resources. Existing records are never reset. Database recovery, security and migration evidence will be linked below once executed in this release.

## Primary market and honest availability

The primary reference is [**DraftKings Predictions → Sports → NFL**](https://predictions.draftkings.com/en/markets/football/nfl), not DraftKings Sportsbook. The primary workflow must not silently replace missing DraftKings contracts with another exchange or American sportsbook odds. An authorized DraftKings feed is not configured in the current environment. Public alternatives retain their actual provider identity and require explicit source selection. No live price, injury or probability is fabricated. The verified public fee disclosure supplies a versioned standard-pricing reference; it does not supply live contract IDs, executable quotes or account-specific execution fees. See [the source access audit](reports/v7-draftkings-access-audit.json).

Percentage display, executable bid/ask, fees, thresholds, Yes/No direction and settlement rules are distinct fields. Unknown cost or payout exceptions withhold after-cost expected value. Conditional historical-usage simulations are not relabeled unconditional contract fair value. Calibrated probabilities require an approved artifact backed by sufficient prospective evidence; no such claim follows from merely increasing Monte Carlo count.

## Implemented behavior and executed checks

Local verification completed on the frozen runtime:

- 501 TypeScript unit checks passed; the final production Next.js build and TypeScript compilation passed.
- 103 Python tests passed, including 10,000/50,000/100,000 complete-game modes.
- All 80 distinct desktop/iPhone-sized browser checks passed. Two initial artifact-collision failures were rerun in isolation and passed; the focused UI checks overlap this set and are not added to inflate the total.
- All 19 managed SQL migrations and compatibility checks passed local PostgreSQL verification; the live migration manifest matches native versions and SQL hashes.
- Built public client assets passed an exact known-credential/QA-value byte scan: 94 assets, 2.42MB, zero matches. Source archives pass integrity, path and configured-credential checks.
- The four-game, 20-definition historical audit remains explicitly retrospective, with Brier 0.2896930985 and log loss 0.8011373769664702. It is **not promoted** and does not establish prospective calibration or market advantage.

Actual production acceptance is in progress. No unrun private-account workflow or physical iPhone installation is claimed.

## Install

Open https://gridiron-ai-gray.vercel.app in Safari on iPhone, then **Share → Add to Home Screen → Add**. Guests can browse public NFL research. GRIDIRON AI sign-in protects Wallet and personal records; a Supabase dashboard account is never required.

See [iPhone installation](IPHONE.md), [operator configuration](ENV_V7.md), [model lab](PLAYER_PROPS_MODEL_LAB.md), [prior v6 delivery](DELIVERY_V6.md) and [source/developer launch](../README.md). Downloaded source files do not execute a backend on iPhone.
