# GRIDIRON AI 5.0 server configuration

This is operator documentation. End users open the hosted app, browse as guests and sign in to GRIDIRON AI only for personal records. The consumer interface does not require a database dashboard, datasets or provider-key configuration.

The deployment reuses the existing Vercel project and Supabase project `qdtdjbapdipopncklsdb`. Do not initialize a replacement project or reset existing tables to repair configuration.

| Name | Server purpose and preservation rule |
| --- | --- |
| `APP_URL` | Canonical HTTPS application origin: `https://gridiron-ai-gray.vercel.app`; used for secure cookies and redirect/CSRF validation. |
| `DATA_BACKEND=supabase`, `GRIDIRON_CLOUD_ONLY=1` | Keep hosted private records in persistent PostgreSQL; a stale device cookie must not select ephemeral SQLite. |
| `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY` | Existing project endpoint and publishable API key. Authenticated private calls supply the verified user's token; RLS remains enforced. |
| `GRIDIRON_PUBLIC_INGEST_TOKEN` | Dedicated server-only capability for trusted shared NFL writes and refresh. Its SHA-256 verifier is stored in a private database schema. It is configured as an encrypted production-only Vercel variable, never a client value. |
| `CRON_SECRET` | Reserved authenticated operator refresh capability. The existing project had none, so v5 provisioned an encrypted production-only value. The database schedule uses one-use HMAC headers instead of queueing this durable token. Existing configured secrets must not be overwritten silently. |
| `SIMULATION_SERVICE_URL` | Generated private web-to-Python Vercel binding. Never hardcode a deployment hostname or manually replace the binding. |
| `SIMULATION_SERVICE_TOKEN` | Existing stable private compute token and model/result proof secret. Keep it unchanged so historical signed results remain verifiable. |
| `GRIDIRON_ASYNC_SIMULATIONS=1`, `GRIDIRON_WORKER_REQUEST_LIFETIME=1` | Existing private-job request-lifetime support. New public research also runs on backend compute, not the iPhone. |
| `GRIDIRON_COMPACT_API=1` | Existing bounded transport support for large owned artifacts and streamed encrypted exports. |
| `OPENAI_API_KEY`, `OPENAI_MODEL` | Optional operator-controlled conversational provider. If absent, source-based research briefs remain identified as evidence briefs; no fabricated language-model response is substituted. |
| `DEVICE_TOKEN_ENCRYPTION_KEY` | Retained private native registration secret; its presence does not establish Apple signing or push delivery. |

No service-role key is sent to the browser. Shared NFL operations use their dedicated server capability; this does not grant access to personal ledgers, conversations or private forecasts. Apple sign-in is exposed only when the actual authentication provider reports it enabled. Do not weaken email confirmation, token verification or RLS to avoid provider configuration.

## Background refresh

Vercel Hobby cron expressions may run once per day only. Do not configure a frequent Vercel cron or split many daily jobs to bypass that plan restriction. The v5 scheduled refresh uses the existing database's supported Cron/HTTP facilities when enabled: the encrypted capability stays in Supabase Vault, and the fixed-origin invocation is executed through a server-only function. The managed HTTP queue can be readable through inherited provider ACLs, so it must contain no durable bearer capability. Scheduled requests carry only a short-lived, one-use HMAC over a timestamp and nonce. The app verifies it in constant time and rejects replays; it grants only the fixed public refresh operation. Application roles cannot read decrypted Vault secrets or call private signing functions.

The refresh pipeline compares meaningful evidence fingerprints and reuses fresh cached results. A collection timestamp alone must not trigger a new simulation. Requests from normal users can revalidate stale public research without any privileged credential in the browser.

GitHub source/CI access does not imply Actions secret-administration access. The connected token's actual repository-public-key request returned 403, so a scheduled GitHub secret was not installed through that unavailable scope. No paid service was started to work around it.

## Deployment and recovery boundaries

Environment changes become active in the next deployment. Preserve existing credentials and the same database project across releases; public cache upgrades do not reset private data. Record the prior deployment ID before releasing and verify both guest access and authenticated owner isolation afterward.

Complete encrypted account export/decryption is tested, including archives larger than the ordinary response gateway limit. Vercel's 4.5MB request limit still applies to a one-shot archive upload; large hosted web restore and complete normalized warehouse/Auth/Storage reconstruction are separate unfinished capabilities. Provider backup/PITR retention is not established by a connected plugin or a healthy database.
