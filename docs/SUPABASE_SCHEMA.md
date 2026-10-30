# Supabase cloud schema and recovery

The cloud migration is additive to a newly provisioned Supabase project. It does not alter, delete, or replace the existing SQLite database. The existing application can continue running in its configured local mode while a cloud migration is prepared. Runtime configuration must select one primary backend explicitly; a cloud failure must not silently write to a local replacement.

## Applied schema sources

The files under `supabase/migrations/` are ordered and their SQL is immutable after application. The connected Supabase migration tool assigned the authoritative live versions. Final source filenames were aligned to those recorded versions without changing a byte of SQL; `supabase/migration-manifest.json` retains the original authoring versions and checksums. No remote migration history or user data was rewritten. The current source versions match the connected project, so an authorized linked CLI should see the five existing migrations rather than try to replay them. Always inspect migration history before a push.

Applied migrations:

- `20261030154518_gridiron_v4.sql`: user-owned relational tables, RLS, precise transactional ledger, cloud records and idempotent account migration.
- `20261030155320_gridiron_financial_export.sql`: complete owner-scoped financial export using the v2 recovery field names.
- `20261030155321_gridiron_index_deduplication.sql`: removes only redundant non-constraint indexes with exactly equivalent keys, predicates, expressions, operator classes and collations. Unique/primary/constraint indexes and distinct foreign-key coverage remain.
- `20261030155322_gridiron_contract_identity.sql`: serializes snapshots by owner/contract and rejects changes to established event, threshold, operator, or settlement rules, including concurrent imports.
- `20261030164434_gridiron_saved_research_restore.sql`: validates each saved-research kind and restores its runtime namespace without changing the source archive, financial import checks, ownership, or existing records.

A later repair must be a new migration. Do not rewrite an applied file, run a destructive reset, or replace the production project to resolve an error.

## Relational domains

User records include profiles/settings, preferences, notification settings, watchlists, saved research, conversations and messages. Supabase Auth owns authentication identities and sessions in its protected `auth` schema; the application does not expose or duplicate session secrets in public tables.

Financial data uses sportsbook accounts, ledger entries, balanced postings, wagers, wager legs, settlements, reconciliation records, audit logs and import receipts. Starting balances, deposits, withdrawals, transfers, credits, refunds and adjustments are distinct journal types, rather than redundant balance tables that could be double-counted. `numeric(20,0)` stores integer cents exactly; SQL arithmetic never converts monetary values to floating point. Gross returned payouts include stake exactly once. Pending stake moves from cash to escrow, and settlement removes escrow before posting cash/P&L. Displayed total bankroll includes escrow; available balance excludes it.

NFL data includes seasons, teams, players, games, plays, team/player statistics, usage, depth charts, coaching tendencies, injuries/practice availability and weather. Composite `(entity_id,user_id)` foreign keys prevent linking another owner's data even when its identifier is known. Source, collection/event/availability timestamps, versions and reliability fields preserve provenance. Unknown historical availability remains null rather than a fabricated publication time.

Market data includes providers, events, contracts, quotes and outcomes. Research data includes feature snapshots, model versions, training runs, simulation runs/scenarios/distributions, predictions, audits, backtests, calibration buckets, reports and paper positions. Flexible legacy-shaped records are retained under `gridiron_records`; the runtime applies domain validation before storage and immutable histories reject updates.

These tables are storage capability, not evidence that a licensed feed, a trained model, or a complete historical dataset exists. Data coverage must be reported independently.

## RLS and privilege boundary

Every application table in `public` enables RLS. Policies compare the authenticated `auth.uid()` with `user_id`, including both `USING` and `WITH CHECK`. Anonymous access is revoked. Owner/time and foreign-key indexes support scoped queries. No frontend code needs a service-role credential.

Direct financial writes are revoked from authenticated clients. Public financial RPCs are security-invoker wrappers around narrowly scoped functions in the unexposed `gridiron_private` schema. Those private security-definer functions are necessary to enforce atomic postings without granting clients unrestricted posting inserts. Every entry point derives the owner from `auth.uid()`, checks it explicitly, never accepts an owner identifier, pins an empty search path and locks that owner's transaction stream. A real JWT's `session_id`, when present, must still exist for the same owner in `auth.sessions`, so revoked sessions cannot keep issuing financial RPCs with an unexpired token.

Historical quotes, prediction snapshots, settlements, injuries and replay inputs cannot be overwritten or retagged to evade immutability. Owner-requested whole-account deletion remains possible through the controlled deletion path. Normal simulation-job status records remain mutable.

## Runtime RPC contracts

- `gridiron_ledger()` returns existing frontend-compatible accounts, transactions, wagers, summary, chart, audit and market/book performance JSON.
- `gridiron_post_transaction(payload)`, `gridiron_place_bet(payload)`, `gridiron_settle_bet(payload)`, `gridiron_reverse_transaction(payload)` perform one atomic operation with exact amounts and ownership checks.
- `gridiron_update_settings(payload)` validates timezone, theme, notification values and monthly stake limits.
- `gridiron_import_transactions(payload)` atomically imports up to 500 rows. An import ID plus row ordinal provides a generated reference when source references are missing; conflicting retries are rejected.
- `gridiron_reconcile(payload)` records statement-versus-available balance without silently changing money.
- `gridiron_consume_rate_limit(payload)` records owner-scoped rate buckets with bounded windows.
- `gridiron_export_financial()` returns every owned journal, posting, wager and audit row without display pagination.
- `gridiron_import_backup(payload,import_hash)` imports a decrypted v2 account backup atomically, as described below.
- `gridiron_delete_own_data()` deletes application data only. It does not pretend to delete Supabase Auth identities.

Supabase-hosted `delete-account` verifies the caller's access token through Auth, requires explicit `DELETE`, globally revokes that session's tokens, and deletes only the authenticated user through the injected server admin credential. It never accepts a target user ID. The app server/browser does not receive the admin credential.

## Migration from the existing account

1. Keep the original SQLite volume, signing configuration and the source recovery checkpoint intact. Create a consistent SQLite snapshot and an encrypted account export before any account migration.
2. Sign into the intended Supabase account. A different device must use that same hosted backend/account.
3. Submit the encrypted v2 backup to the authenticated migration endpoint. The runtime authenticates/decrypts it and computes a SHA-256 import receipt; passwords, session records and provider secrets are never imported.
4. SQL requires a complete raw journal/posting/wager export and an empty destination financial workspace. It validates each journal's balance, source identifiers and exact cents, then imports financial records and their original dates/outcomes, settings, preferences, conversations, research, predictions and simulation replay inputs. Source UUIDs are preserved; ownership is remapped to the authenticated cloud user.
5. Before commit, the imported bankroll and realized P/L must exactly reconcile with the authenticated source export. Any exception rolls the entire import back. The original decrypted export is also retained as an owner-protected cloud archive for recovery of less-structured records.
6. Retrying the same verified import hash is a no-op with `duplicate:true`. A different import into a nonempty financial workspace is refused rather than merged or reset. Retain both copies until reconciled.

Saved research imported before the namespace repair may remain under the older generic `research_records` kind and be absent from normal saved-research queries. The repair does not guess or rewrite those existing rows. Recover each original kind from the corresponding owner-protected `legacy_backup_archive.data.research.research_records` or the original encrypted backup, reconcile identifiers, and use a deliberate additive recovery operation. Do not delete a completed financial import or reset the destination to retry it. New imports restore `research_records/<original-kind>` individually and retain the complete original payload unchanged.

## Recovery and backups

Use complete encrypted account exports and retain an off-host, access-controlled copy of the original SQLite checkpoint. Project backup/PITR availability depends on the Supabase plan; a connected project is not a guarantee of retention or restore entitlement. Verify the actual project's backup settings and test restoration into a separate authorized environment before relying on it.

To recover, preserve the failing state and logs, verify a backup copy, restore into an isolated destination, reconcile subsequent writes and switch traffic only after account/balance checks. Do not overwrite the only database copy or run `supabase db reset` against user data.

## Executable verification

`supabase/tests/verify-local.mjs` uses PGlite (PostgreSQL in WASM) with synthetic Auth fixtures to compile every SQL migration and run real PL/pgSQL ledger/RLS/import/export checks. It requires pinned development dependency `@electric-sql/pglite@0.5.13` and runs from the project root:

```sh
node supabase/tests/verify-local.mjs
```

`supabase/tests/live-rls.sql` performs owner isolation and financial arithmetic checks against the real authorized project in a transaction containing only temporary synthetic user IDs and rolls everything back. Run it through an authorized administration SQL tool, not an application endpoint. It does not send email or create durable test accounts. These checks supplement actual Supabase Auth SDK sign-in testing; they are not a replacement for it.

Run Supabase security/performance advisors after migrations. Report actual executed results separately from supplied commands. A parsed SQL file alone is not proof that RPCs, live Auth or cross-device persistence work.
