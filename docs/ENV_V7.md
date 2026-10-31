# GRIDIRON AI 7.0 operator configuration

End users open the hosted application. Normal NFL and player-prop research does not require a CSV, manually entered statistics, database dashboard or provider-key configuration.

Keep the existing Vercel Services project and Supabase project `qdtdjbapdipopncklsdb`. The web/API service and private Python worker retain their server credentials. Do not create a replacement database, reset records, rotate existing signing keys casually or expose service-role credentials to a browser.

## Primary market: DraftKings Predictions event contracts

These optional values belong only in encrypted server configuration:

| Variable | Purpose |
| --- | --- |
| `GRIDIRON_DK_PREDICTIONS_FEED_URL` | An explicitly authorized partner/feed endpoint returning the validated `gridiron-nfl-event-contracts-v1` envelope. The earlier `gridiron-player-prop-contracts-v1` player-only envelope remains supported. This is an adapter contract, not a claim that DraftKings publishes a public API. HTTPS and safe source URLs are required. |
| `GRIDIRON_DK_PREDICTIONS_FEED_TOKEN` | Optional server-side bearer credential for that authorized endpoint. Never put it in the URL, client bundle, repository or screenshot. |
| `GRIDIRON_DK_PREDICTIONS_FEED_AUTHORIZED=1` | Operator attestation that access and downstream use are authorized. Missing attestation leaves the feed unavailable. It does not create a license, account or entitlement. |

The current environment has no authorized DraftKings Predictions feed. The publicly reachable site and NFL navigation are not an authorized executable-contract API; the documented access audit is retained in `docs/reports/v7-draftkings-access-audit.json`. The application identifies this limitation for the primary workflow. The requested market is **DraftKings Predictions → Sports → NFL**, at https://predictions.draftkings.com/en/markets/football/nfl; it is not DraftKings Sportsbook. Percentage-based display prices do not establish executable cost, fees or payout rules. Public Kalshi NFL event contracts are an explicitly selected, separately labeled alternative, with exact participant IDs, thresholds, rules and observed bid/ask data. They are not relabeled as DraftKings contracts. Quote observation does not guarantee an executable fill. Missing fees and unsupported non-participation/fair-price exceptions withhold unconditional expected value.

See the strict schema and source checks in [providers.ts](../lib/player-props/providers.ts), [game-markets.ts](../lib/player-props/game-markets.ts) and [normalize.ts](../lib/player-props/normalize.ts). Optional user-verified manual snapshots stay private and are not described as live prices.

## NFL research API and source selection

The consumer workflow uses **GET `/api/nfl/markets`** and **POST `/api/nfl/markets/analyze`**. The existing player-prop endpoints and private `/api/markets` import/history operations remain preserved. Source selection is explicit: the primary is `DraftKings Predictions`; `Kalshi` is a named alternative. Available research scopes are `all`, `player` and `game`. Supported rankings are coverage, calibrated probability, model-market difference, historical reliability, uncertainty, injury changes and market movement. Unsupported rankings show insufficient evidence instead of inventing values.

The authorized all-NFL envelope supports the existing player fields plus four exact game statistics: `gameWinner`, `spread`, `totalPoints` and `teamTotal`. A definition includes the scheduled game, team where relevant, finite threshold, comparison operator, full-game/overtime flags, verified settlement terms and normal payout. Winner definitions require explicit tie settlement. Integer thresholds, strict versus inclusive comparisons, reversed No outcomes and tie payouts are not silently normalized into a different contract. A winner contract with a partial tie payment reports win, loss, tie probability and expected settlement value separately; the two full-payout probabilities are not mislabeled complements. Regulation-only, quarter/half or otherwise unsupported definitions are withheld.

Displayed Yes/No percentages, bid/ask prices, last trade, liquidity, fees and source timestamps remain separate. A source observation is not a promised executable fill. The provider adapter rejects inconsistent identities, crossed prices, stale/future quotes, mismatched thresholds, unknown rules and credential-bearing source URLs. The exact fee-rounding protocol is retained, including `collateral_total_up_to_cent` where the verified definition requires purchase collateral and fees to be rounded together. A manual capture never becomes a live feed simply because its timestamp is recent. Exact cost-dependent value remains unavailable when fees or exceptional settlement rules are unsupported.

## Published DraftKings standard fee reference

The public [DraftKings Predictions fee disclosure](https://myaccount.draftkings.com/documents/fee-disclosure?product=predict) was retrieved and version-checked in [the access audit](reports/v7-draftkings-access-audit.json). The read-only `/api/nfl/pricing` calculator uses the verified standard schedule only when supplied a known venue, price, quantity and supported execution basis. CME and CDNA/DKeX have different schedules; fractional-cent tiers and whole-transaction rounding are retained. An older promotional broker-only fee is not used as the total current cost.

This calculator is a cited **standard-cost estimate**, not a discovered market quote, actual fill, eligibility check or guarantee of an account's fee arrangement. Unknown venue, negotiated pricing, missing execution facts or an unverified reference withhold the estimate. The calculator does not populate live contract prices or bypass missing data credentials. Wallet continues to record the actual fee and actual total debit from a user's receipt.

## Persistence and background work

The existing server-only `GRIDIRON_PUBLIC_INGEST_TOKEN` authorizes narrow shared-football writes. Its verifier remains in a private database schema. The existing authenticated Supabase Cron/HTTP callback retains its one-use signing protocol; no durable token enters the HTTP queue. The same persistent database stores immutable predictions, quote history, research runs, resolutions and model candidates. By default the scheduler does not discover a replacement provider when DraftKings is unavailable. `GRIDIRON_KALSHI_BACKGROUND_RESEARCH=1` is a separate operator opt-in for creating new Kalshi background research runs; it is off unless explicitly set. An already queued, explicitly selected alternative research run may finish without enabling future alternative-provider scans. Personal Wallet records, saved combinations and conversations remain protected by app identity and ownership policies.

The bounded application admission policy allows **500,000 primary complete games per UTC day**. This supports refreshed exact player distributions across a full NFL slate without erasing prior usage or snapshots. It does not change a provider plan, purchase resources or bypass a hosting quota. Cache reuse, supported counts, worker deadlines, input validation and rate limits still apply. The host may refuse work when its own limits are reached. Parameter-bootstrap simulations are separately identified from the primary sample count.

## Model development and rollback

Calibration requires sufficient verified prospective training and separate chronological holdout evidence. Current raw simulation probabilities must not be relabeled calibrated while that evidence is absent. Research resolutions do not imply that an exchange has paid a contract.

The optional server-only `GRIDIRON_PROP_CALIBRATOR_SELECTION` selects an existing approved artifact for a `category|modelVersion` scope; a null selection disables calibration for that scope. An invalid selection withholds calibration. It is an operator rollback control, not end-user setup. See [the model-lab protocol](PLAYER_PROPS_MODEL_LAB.md).

## Assistant and identity boundaries

`OPENAI_API_KEY` enables optional conversational research only when an operator configures it. Missing language-model credentials do not prevent sourced prop briefs or exact personal withdrawal, deposit, realized P/L and balance reports. Those private reports are calculated directly from the authenticated owner's ledger, use the account timezone, persist to conversation history, and identify themselves as `calculated_account_report` with `generatedByAI: false`.

The public health endpoint reports only selected-provider credential presence as `configuration.assistant`, with `assistantStatus.generationVerified: false`. This does not verify generation readiness, budget, entitlements or tool execution. Public health never probes private credit balances. Existing AI Gateway configuration is preserved without enabling paid use; its private credit/authorization checks remain separate. General language-model conversation remains unavailable without a usable, authorized provider. Apple sign-in and the existing confirmation-email return-URL issue remain separate operator Auth configuration requirements. Never bypass confirmation or row-level security to hide that limitation.

## Recovery

The pre-upgrade checkpoint includes a verified Git bundle and an encrypted, consistent database snapshot with local decrypt verification. A separate pre-v7 source checkpoint also preserves the existing v6 archive and Git history. Secrets and plaintext records stay outside Git. Additive source migration filenames match the actual managed migration history; their SQL bytes are retained. Roll back application code or select an earlier approved model without deleting research snapshots, changing user ownership or resetting financial records. A source ZIP is not a substitute for full database/Auth/Storage recovery or verified provider backup retention.

## Current combination scope

The preserved authenticated joint-outcome lab supports eligible player outcomes from the same coherent simulated game. Unsupported game-contract combinations are withheld. A joint simulation probability does not establish that DraftKings will accept a combined purchase or pay a traditional sportsbook parlay. Actual combination payouts remain unavailable without verified platform combination and settlement terms.

## Current capacity block

The free database currently occupies about 450.22MB and its 450MB public-research reserve guard has activated. New public simulations/research writes are paused; saved research and Wallet remain available. Live immutable predictions and quote history account for most usage, and the safe ordinary maintenance reclaimed only about 196KB. Do not delete history or waive the financial reserve to make an acceptance test green. Completing the full slate needs additional persistent capacity or an approved durable archive architecture. Current official Supabase Pro pricing starts at $25/month with 8GB database capacity under its published terms; billing/account-owner authorization is required. No paid plan was enabled.
