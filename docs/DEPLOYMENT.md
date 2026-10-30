# Secure deployment: Supabase cloud and preserved legacy storage

GRIDIRON AI now supports two explicit data backends. **Supabase** uses remote PostgreSQL, Supabase Auth, owner-scoped RLS and atomic financial operations. **SQLite** remains a separately selectable legacy workspace so existing personal records are preserved. Switching the selected workspace is not a migration, deletion, reset or promise that both databases contain the same records.

The Supabase database and its account-deletion Edge Function have been provisioned and checked. The Next.js website, private Python service, public HTTPS hostname, Apple signing and physical iPhone installation have **not** been deployed or verified on a production host in this session. A Supabase API URL is not the application's website URL.

## Configured Supabase project

- Project: `gridiron-ai`, reference `qdtdjbapdipopncklsdb`.
- API: `https://qdtdjbapdipopncklsdb.supabase.co`.
- Region/status observed: `us-east-1`, `ACTIVE_HEALTHY`.
- Five versioned SQL migrations in `supabase/migrations/` were applied to the live project.
- SQL verification found RLS enabled on all 47 public tables. Owner isolation and actual authenticated financial operations were checked; see the current delivery report for executed evidence.
- Authenticated `delete-account` Edge Function is active, version 1, with JWT verification enabled. An owned QA deletion was exercised and another owner's records remained intact.
- One provider advisor warning remains: leaked-password protection is disabled. Review [Supabase password security](https://supabase.com/docs/guides/auth/password-security) and enable the supported account/plan control before treating that protection as active. No SQL/RLS advisor finding was reported at the final check.

Do not replay those five migrations blindly or run a database reset against this project. Inspect its existing migration history before appending a new migration. Keep applied SQL immutable. Use the connected Supabase tooling or an explicitly linked, authorized CLI; do not invent a different project when an operation fails.

## Server configuration

Use the provided `.env.example` as a list of configuration names. Production values belong in the deployment platform's secret store or an untracked, tightly restricted environment file. Never copy a local credential file into the website's public assets, native bundle, source ZIP or logs.

| Variable | Production purpose |
| --- | --- |
| `APP_URL` | Actual canonical HTTPS **Next.js application** origin; mutation checks and Secure cookies depend on it. It is not the Supabase API URL. |
| `DATA_BACKEND` | Set `supabase` for a cloud-default deployment. `sqlite` remains the explicit legacy option. |
| `SUPABASE_URL` | The configured project's HTTPS API URL above. |
| `SUPABASE_PUBLISHABLE_KEY` | That project's publishable key. The BFF supplies each verified user's token and RLS applies. Do not supply a service-role/secret key here. |
| `DATA_DIR` | Existing persistent SQLite directory if any legacy workspace is retained; `/data` in the supplied Docker container. |
| `SIMULATION_SERVICE_URL` | Reachable private Python HTTP(S) service; Compose uses `http://quant:8000`. |
| `SIMULATION_SERVICE_TOKEN` | Stable random secret of at least 32 characters, identical in Node and Python. Required for service authorization, signed artifacts and cloud generated-result receipts. |
| `ODDS_API_KEY` | Optional authorized The Odds API key; sportsbook/market coverage depends on entitlement and jurisdiction. |
| `OPENAI_API_KEY`, `OPENAI_MODEL` | Optional server-side research assistant configuration; live provider calls require working credentials. |
| `DEVICE_TOKEN_ENCRYPTION_KEY` | Optional stable server secret of at least 32 random characters for encrypted native APNs registrations. Registration is separate from delivery. |
| `CRON_SECRET` | Legacy operator injury-job authorization only; it does not identify or grant access to a Supabase owner. |

No service-role key is required in the ordinary Next application. The deployed deletion Edge Function uses its platform-provided server-only administrative credential after validating the caller; it never accepts a target user ID from the client and never exposes that credential.

Supabase Auth email-confirmation redirects must permit the real `APP_URL`. Production signups may need email confirmation and provider email delivery. Do not disable authentication or claim that an unconfirmed signup established a session merely to make a login test pass.

## Preserve an existing workspace before changing the default

1. Identify and retain the current `DATA_DIR`, previous image/source, configuration and consistent backup. Never replace a volume with an empty directory to resolve an error.
2. For SQLite, follow [MIGRATIONS.md](MIGRATIONS.md) to create a consistent snapshot including committed WAL state. Keep an encrypted account export as an additional portability copy.
3. Configure the existing Supabase project on the server. Selecting Supabase in Settings sets the HTTP-only `gridiron_backend` preference; an operator may also choose `DATA_BACKEND=supabase` as the default. A per-device explicit preference takes precedence. Cloud failure is reported; local data is never silently substituted.
4. Create or confirm the intended Supabase Auth account. Local passwords/sessions are not copied into cloud authentication.
5. If migration is desired, use the reviewed encrypted-backup import described in [SUPABASE.md](SUPABASE.md). It verifies the target owner, balances and settled P/L and uses an atomic import. Existing cloud financial history causes rejection; an identical completed source hash is an idempotent no-op. The original SQLite database and export remain untouched.
6. Reconcile counts, balances, pending stakes, audit entries and histories before relying on the cloud workspace. Keep the original volume and recovery copy until verification is complete. Signing into the same remote account on another device reads the remote account's data.

The importer retains the complete original typed-table payload but does not yet rebuild every specialized NFL/model warehouse table from it. Do not describe an account import as a full PostgreSQL project restore. See [SUPABASE.md](SUPABASE.md) for the exact restoration boundary.

## Supplied two-service Docker deployment

The supported configuration is a Node application and a private Python service, behind HTTPS. The Node runtime is unprivileged. The Python service is not exposed to the public Internet.

1. Prepare a maintained Linux host with Docker/Compose, a domain and an HTTPS reverse proxy. This may require a paid host; no host purchase or website deployment is claimed here.
2. Copy the source and create a private `.env` using the configuration names above. Set the real HTTPS `APP_URL`, `DATA_BACKEND=supabase`, Supabase URL/key and a stable simulation token. The development template's `http://localhost:3000` must not remain the production origin.
3. Run `docker compose up -d --build`. The app binds host loopback port 3000; the quant service is reachable only on the Compose network as `quant:8000`.
4. The supplied Compose file keeps the `gridiron-data` volume to preserve an available legacy workspace. A pure cloud deployment does not use SQLite as its primary database, but this distribution still permits explicit legacy selection. Retain the old volume, or deliberately restrict legacy access before choosing a stateless host. No stateless legacy-storage compatibility is claimed.
5. Configure the reverse proxy for your actual domain. For example:

```caddyfile
gridiron.example.com {
  reverse_proxy 127.0.0.1:3000
  encode zstd gzip
  header Strict-Transport-Security "max-age=31536000"
}
```

6. Restrict inbound access to HTTPS and trusted administration. Keep 3000 and 8000 private. A personal VPN or identity-aware gateway can further limit access; app authentication and RLS remain necessary.
7. Verify the final HTTPS origin, Secure/HttpOnly cookies, selected backend, account isolation, export and small disposable financial round-trips before storing important records. `/api/backend` reports configured/reachable cloud status without financial data; the authenticated Supabase `/api/status` reports the selected database connection.

Do not run `docker compose down -v` during an upgrade. Do not run multiple Node instances against the same SQLite file or use an unsuitable network filesystem. Cloud PostgreSQL records survive a Node container replacement, provided the same Supabase project/account and configuration are retained. Stateful schedulers and the legacy workspace still need their own durable configuration/storage.

Dockerfiles and Compose are provided; a successful local production build is not evidence that the images have run on your target VPS or that its TLS and routing are correct.

## Quantitative service, workloads and secret continuity

The Python service uses authenticated requests and signed fitted artifacts. Node proxies requests for the authenticated owner and stores inputs, outputs and provenance in that owner's selected database. Python is stateless; it does not need a shared model-directory volume. The stable secret must survive restarts and deployments. Rotating it can invalidate existing model signatures and generated-result receipts, so retain verified backups and plan refitting or proof migration deliberately.

The service bounds input bytes, supports one active fit/simulation at a time and returns explicit unavailable/busy/evidence errors. Existing web simulation requests have a 240-second upstream timeout; the hosting platform, proxy and worker lifecycle must support the requested workload. More expensive advanced-model requests need adequate CPU/memory and their documented timeout. Do not solve capacity failures by silently reducing requested game counts or displaying a stale result as current.

See [QUANT_SERVICE.md](QUANT_SERVICE.md), [SIMULATION.md](SIMULATION.md) and [MODELS.md](MODELS.md). A fitted model is not automatically promoted: historical source availability, chronological validation, uncertainty and promotion checks still govern its use. Monte Carlo precision is separate from model validity. Weather and injury what-if changes require supported evidence; unsupported inputs remain blocked.

## Backups and restore boundaries

- **Supabase project backup/PITR:** availability, retention, paid entitlement and an actual restore drill have not been verified. Inspect the plan's supported backup controls and test recovery to a separate authorized project before making destructive changes. Do not infer PITR merely from a connected plugin or healthy project.
- **Encrypted account export:** logical exports, ownership boundaries, authenticated encryption, full financial reconciliation and replay/history inclusion were tested. Typed exports paginate and reconcile counts; an over-limit or changing export fails rather than pretending a partial archive is complete. This is not a byte-for-byte PostgreSQL backup or proof of full normalized-warehouse reconstruction.
- **Legacy SQLite:** automatic pre-migration snapshots and the explicit backup script use consistent SQLite snapshots including WAL commits. Retain encrypted off-host copies, protect access, verify integrity and restore into a separate directory before switching traffic.
- **Secrets and identity:** keep stable signing/encryption keys in a protected recovery process, separately from exported user data. Account exports intentionally omit passwords, active authentication secrets and provider credentials.

Never overwrite the only recovery copy, reset a project, discard the old volume, or run a destructive migration to force an upgrade through. Recovery procedures are in [MIGRATIONS.md](MIGRATIONS.md) and [SUPABASE.md](SUPABASE.md).

## Owned research scheduling and injury recovery

The configurable research pipeline refreshes only implemented/authorized sources, records availability and timestamps, caches observations and queues evidence-supported work. A configured interval does not provision an always-running scheduler.

For a Supabase workspace, use the owner's signed-in controls or an operator-run `scripts/research-pipeline.mjs` with that owner's private session-cookie file. Restrict it to mode 0600; the script persists refreshed cookies without logging them. An expired session fails explicitly. `CRON_SECRET` alone cannot act as a Supabase user or read all cloud accounts.

For a legacy SQLite deployment, `scripts/run-jobs.mjs` can call the narrowly protected injury queue with the legacy `CRON_SECRET`; retain its documented retry/lease recovery settings. Do not apply that credential path to the cloud workspace as though it had owner identity. External cron infrastructure, unattended user authorization and monitoring must be configured by the operator.

Live DraftKings Predictions access and Hard Rock coverage are not granted by deployment. Exact manual/CSV/verified OCR paths retain their source labels. Do not claim a restricted private API, continuous official injury wire, verified liquidity or market profitability when that source/evidence is unavailable.

## Private native iPhone application

The native app connects to the deployed **Next application origin**, not directly to the Supabase API URL. Set `GRIDIRON_NATIVE_URL` only after the actual HTTPS web app is available. Keep server secrets out of the iOS bundle.

Follow [NATIVE_IPHONE.md](NATIVE_IPHONE.md) for the Capacitor/Xcode project, Keychain session handling and personal development/ad-hoc installation. No App Store or TestFlight distribution is configured. Linux generated and checked native source/assets but cannot compile/sign a genuine IPA. macOS/Xcode, an Apple team/profile and the personal iPhone's provisioning are still required. APNs registration code and encrypted token storage are separate from a configured, physically tested push-delivery service.
