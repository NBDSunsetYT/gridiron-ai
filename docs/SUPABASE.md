# Supabase cloud backend

The application has two explicit backend modes. The existing SQLite workspace remains available and is never silently reset or replaced. Supabase mode uses PostgreSQL as the primary database, Supabase Auth as identity, owner-scoped RLS for every exposed table, and atomic financial RPCs. Browser refreshes, another device, and Node redeployments read the same remote records after sign-in.

## Configure

Set server-only `SUPABASE_URL` and `SUPABASE_PUBLISHABLE_KEY`. Use the modern publishable key. Do not put either key into `NEXT_PUBLIC_*`; no service-role key belongs in the application bundle. A publishable key does not bypass RLS: the backend verifies the current user through `auth.getUser()` and supplies that user's JWT to every data request. The published Next server needs HTTPS and a canonical `APP_URL`. Supabase email-confirmation redirects must allow that origin in project Auth settings.

The authenticated cookies are `gridiron_sb_access` and `gridiron_sb_refresh`: HTTP-only, same-site Lax, Secure on HTTPS, with no credentials in localStorage. Expired access is refreshed through Supabase and the returned identity is verified before use. Production email signups can require confirmation; no session is claimed until confirmation/sign-in succeeds.

The cloud project is selected using the Settings connection control, which sets the HTTP-only `gridiron_backend` routing cookie, or an operator can set `DATA_BACKEND=supabase`. `sqlite` remains the legacy workspace option. Middleware routes cloud API requests to `/api/cloud/*`. Direct cloud API requests also work. Missing cloud configuration or a cloud outage fails explicitly; it never substitutes a local database.

## Data and financial integrity

All five versioned `supabase/migrations/` files have been applied to the live project, including the additive saved-research namespace restore repair. Applied files remain immutable. They define owner-scoped relational financial, research, NFL, market and model tables. Financial writes use authenticated atomic RPCs rather than direct table writes. Money is integer numeric cents; ledger postings balance within the transaction. Transfers do not create income; deposits and withdrawals do not create betting P/L. Unique references/idempotent import receipts prevent duplicate cash movements. New contract history is append-only, and a PostgreSQL trigger serializes exact contract identity/rule checks under concurrent imports.

Flexible existing application histories use the RLS-protected `gridiron_records` adapter alongside normalized financial tables. This preserves current UI contracts without pretending every imported historical dataset is already populated into specialized warehouse tables. Unknown or unconnected NFL/provider datasets remain absent.

Cloud result records also contain a server HMAC receipt bound to the owner, job identifier and exact result. RLS protects who can access a record; the receipt separately prevents user-editable JSON from being presented as an authenticated generated simulation. Imported legacy outcomes remain retained and exportable, but unauthenticated generated-result displays and attachments are withheld until rerun through the private service. Keep the server simulation secret stable across deployments; rotating it requires a deliberate artifact/proof migration or refit/rerun.

Large simulation input/result leaves use lossless gzip JSON transport inside the owner's JSONB record. Status, job kind, timestamps, claim metadata and contract identities remain directly readable. Reads and encrypted exports restore the full original JSON; SHA-256, declared byte counts and a 20 MB decompression bound reject corrupt or oversized payloads. The encoding does not replace encryption or server result attestation. Supabase requests have a 60-second deadline, and automatic PostgREST retries are disabled to avoid replaying ambiguous financial writes. Complete large fitted models can be referenced by their owned attested `modelJobId` when running a simulation instead of uploading the artifact again.

## Preserve and migrate an existing account

1. Keep the original DATA_DIR, consistent SQLite backup, previous source/image, and server configuration. Switching the selected backend does not migrate or delete the old workspace.
2. In the old workspace, export an encrypted account backup. It contains raw balanced financial postings, wagers, audit entries, research, conversations and simulation replay inputs, without passwords or active sessions.
3. Create/confirm a Supabase Auth account and select the cloud workspace. Import the encrypted backup through Settings. The server authenticates the target cloud account, decrypts the supplied archive, validates balances/settled P/L, and calls one atomic import RPC. Existing cloud financial records cause rejection; an identical previously completed source hash is a no-op. The source SQLite database and archive are unchanged.
4. Reconcile account balances, pending exposure, realized P/L, transaction counts and historical records before adopting cloud mode. Keep the recovery checkpoint until that check is complete. Do not re-enter returned stakes as fresh deposits.

A CLI uses the same authenticated endpoint:

```text
node --import tsx scripts/migrate-cloud.ts https://your-app.example encrypted-backup.json
```

Provide a single JSON object on stdin containing `email`, `password`, and `backupPassword`, using a trusted password manager or hidden-input workflow. Never put these values in arguments, shell history or a committed file. The CLI writes no secret file, does not alter the source archive, and revokes its temporary session when possible.

## Backups and deletion

Encrypted cloud account exports page all owned research/messages and include full raw financial data through a dedicated export RPC. `research.typedTables` also contains all 43 owner-scoped normalized financial, NFL, market and model table families, including play-by-play records. Pagination checks exact counts and advances by the actual returned row count, so a project row cap cannot silently truncate an archive. The financial snapshot is reconciled before return. Exports above the supported memory bound fail explicitly instead of returning an apparently complete truncated archive. The expanded account bound is 160 MB, including complete historical replay inputs and fitted rows. Archives of at least 1 MB use a version-2 envelope with lossless gzip before AES-256-GCM encryption; envelope metadata is authenticated and decompression is bounded. Small exports retain version 1, and both versions can be decrypted. The ciphertext remains bounded at 100 MB of base64. Large encrypted responses stream through the hosted API without caching private data.

Export and import are different limits: the browser import selector currently accepts files below 60 MB, the cloud import route has a 100 MiB application request bound, and the hosting/provider request limit can be lower (Vercel buffered requests are limited to 4.5 MB). A large downloadable archive is not proof that the same archive can be uploaded or fully reconstructed through an interactive route; use the documented project recovery procedure when those limits apply.

The current account import restores financial and compatible app histories (including saved-research/watchlist namespaces repaired by migration five), and retains the complete original typed-table payload in the owner's imported source archive. It does **not** yet rebuild every normalized NFL/model table from that payload. Use the project-level restore procedure or a deliberate typed-data importer for normalized warehouse recovery. No typed records are discarded from the exported archive, and an archive-only restore must not be described as a complete normalized database restore.

An account export is not a full PostgreSQL recovery point: use the Supabase plan's supported project backup/PITR procedures, encrypted off-site exports and verified restore drills. Retention and backup availability depend on the project plan; no paid feature is claimed merely because the integration is connected.

Cloud account deletion invokes a deployed authenticated `delete-account` Edge Function. It verifies the caller, revokes that caller's sessions and uses an Edge-only admin credential to delete only their Auth identity; cascades remove owned data. No admin credential reaches the browser or ordinary Next application. Without the function, deletion reports unavailable rather than falsely claiming success. Local account deletion remains separate from the remote account.

## Verification scope

Unit tests cover provider verification, refresh/cookie handling, no-local-fallback behavior, deterministic reviewed imports and generated-result tamper resistance. Remote role/RLS, financial RPC and actual password-session checks must be reported from their executed results in the final delivery report. Email delivery, mobile network behavior and project restore procedures require their corresponding external infrastructure and are not established by a passing unit test.

The native APNs registration endpoint stores only an AES-GCM encrypted token under the authenticated owner when `DEVICE_TOKEN_ENCRYPTION_KEY` is configured. Token registration does not mean APNs delivery or Apple signing has been configured.
