# GRIDIRON AI 6.0 operator configuration

End users open the hosted application. Normal player-prop research does not require a CSV, manually entered statistics, database dashboard or provider-key configuration.

Keep the existing Vercel Services project and Supabase project `qdtdjbapdipopncklsdb`. The web/API service and private Python worker retain their server credentials. Do not create a replacement database, reset records, rotate existing signing keys casually or expose service-role credentials to a browser.

## Authorized DraftKings event-contract access

These optional values belong only in encrypted server configuration:

| Variable | Purpose |
| --- | --- |
| `GRIDIRON_DK_PREDICTIONS_FEED_URL` | An explicitly authorized partner/feed endpoint returning the validated `gridiron-player-prop-contracts-v1` event-contract schema. This is an adapter contract, not a claim that DraftKings publishes a public API. HTTPS and safe source URLs are required. |
| `GRIDIRON_DK_PREDICTIONS_FEED_TOKEN` | Optional server-side bearer credential for that authorized endpoint. Never put it in the URL, client bundle, repository or screenshot. |
| `GRIDIRON_DK_PREDICTIONS_FEED_AUTHORIZED=1` | Operator attestation that access and downstream use are authorized. Missing attestation leaves the feed unavailable. It does not create a license, account or entitlement. |

The current environment has no authorized DraftKings Predictions feed. The application identifies this limitation. Public Kalshi NFL event contracts are a separately labeled alternative, with exact participant IDs, thresholds, rules and observed bid/ask data. They are not relabeled as DraftKings contracts. Quote observation does not guarantee an executable fill. Missing fees and unsupported non-participation/fair-price exceptions withhold unconditional expected value.

See the strict schema and source checks in [providers.ts](../lib/player-props/providers.ts) and [normalize.ts](../lib/player-props/normalize.ts). Optional user-verified manual snapshots stay private and are not described as live prices.

## Persistence and background work

The existing server-only `GRIDIRON_PUBLIC_INGEST_TOKEN` authorizes narrow shared-football writes. Its verifier remains in a private database schema. The existing authenticated Supabase Cron/HTTP callback retains its one-use signing protocol; no durable token enters the HTTP queue. The same persistent database stores immutable predictions, quote history, research runs, resolutions and model candidates. Personal Wallet records, saved combinations and conversations remain protected by app identity and ownership policies.

V6's bounded application admission policy allows **400,000 primary complete games per UTC day**. This supports refreshed exact player distributions across a full NFL slate without erasing prior usage or snapshots. It does not change a provider plan, purchase resources or bypass a hosting quota. Cache reuse, supported counts, worker deadlines, input validation and rate limits still apply. The host may refuse work when its own limits are reached. Parameter-bootstrap simulations are separately identified from the primary sample count.

## Model development and rollback

Calibration requires sufficient verified prospective training and separate chronological holdout evidence. Current raw simulation probabilities must not be relabeled calibrated while that evidence is absent. Research resolutions do not imply that an exchange has paid a contract.

The optional server-only `GRIDIRON_PROP_CALIBRATOR_SELECTION` selects an existing approved artifact for a `category|modelVersion` scope; a null selection disables calibration for that scope. An invalid selection withholds calibration. It is an operator rollback control, not end-user setup. See [the model-lab protocol](PLAYER_PROPS_MODEL_LAB.md).

## Assistant and identity boundaries

`OPENAI_API_KEY` enables optional conversational research only when an operator configures it. Missing language-model credentials do not prevent sourced prop briefs or exact personal withdrawal, deposit, realized P/L and balance reports. Those private reports are calculated directly from the authenticated owner's ledger, use the account timezone, persist to conversation history, and identify themselves as `calculated_account_report` with `generatedByAI: false`.

General language-model conversation remains unavailable without a configured provider. Apple sign-in and the existing confirmation-email return-URL issue remain separate operator Auth configuration requirements. Never bypass confirmation or row-level security to hide that limitation.

## Recovery

The pre-upgrade checkpoint includes a verified Git bundle and an encrypted, consistent database snapshot with local decrypt verification. Secrets and plaintext records stay outside Git. Additive source migration filenames match the actual managed migration history; their SQL bytes are retained. Roll back application code or select an earlier approved model without deleting research snapshots, changing user ownership or resetting financial records. A source ZIP is not a substitute for full database/Auth/Storage recovery or verified provider backup retention.
