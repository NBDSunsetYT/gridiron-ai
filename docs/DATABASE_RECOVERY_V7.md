# GRIDIRON AI database preservation

The existing project is `qdtdjbapdipopncklsdb`. The upgrade applies versioned migrations without resetting accounts, journal entries, wagers, conversations, predictions or public research. The migration manifest records each native application version and the exact SQL SHA-256.

## Verified checkpoint

A fresh encrypted checkpoint was captured on 2026-10-31 before private financial acceptance tests and before the game-market and fractional-fee migrations. It contains **49 current private/account, financial and user-scoped table families, including `auth.users` and `auth.identities`**. All tables were read in one statement snapshot. Local GPG decryption and every table's row count were verified in memory; plaintext was not written to disk.

The private directory is `/workspace/gridiron-recovery/20261031T044810Z-v7-before-markets/`. It contains `database.pgp`, a separate `checkpoint.key`, and `manifest.json`. The directory is mode 0700 and its files are mode 0600. The key and archive are excluded from source packages and Git. A second encrypted copy is retained in the unexposed `gridiron_shared_private.recovery_checkpoints` table; clients have no table grants or RLS policies.

Ten shared public research/cache table families are excluded from this fresh checkpoint. Attempts to export all current public research hit resource/time bounds and rolled back; they are **not** successful backup claims. The prior verified pre-v6 public/Auth checkpoint is retained, and newer shared research remains in its append-only production tables. This checkpoint does not establish complete provider Auth/Storage reconstruction, database restore success, automated provider retention or PITR coverage.

To verify an archive, use GPG with the separate key file, parse the decrypted JSON in memory, and compare every table length with the manifest. Never paste decrypted Auth records into logs, issue comments or the public repository. Do not import Auth rows or blindly replay a financial archive into a running account. Recovery requires an operator to inspect the target schema and journal identities, choose the supported account import/Admin Auth flow, verify idempotency and reconciliation in an isolated target, and authorize any destructive operation separately. No database restore was performed for this upgrade.

## Storage and rolling releases

The current organization uses the existing free tier. New public contracts, prediction snapshots and full shared game jobs/results stop being admitted at **450,000,000 database bytes**, retaining headroom for personal records. Existing cached results and fenced failure checkpoints remain available. The guard does not change hosting plans, purchase storage, delete history or block the private financial ledger. Its boundary and private financial availability were tested in a disposable local PostgreSQL instance.

New v7 snapshots store exact immutable contract rules and prices through their quote foreign key. Capture-specific identity, verification, observation clocks and liquidity remain in the snapshot overlay. Older snapshots are not rewritten. Compaction requires the explicit `nfl_market_snapshot_v7` request marker, so a v6 writer retains its full format during deployment. Once v7 compact records exist, use a compatible reader for a rollback; an old v6 reader cannot hydrate the new format.

## Account configuration still requiring operator access

Confirmed email/password sign-in and owner isolation were independently tested through the application. A synthetic invalid-token probe, without sending email, still found that the Auth verification endpoint falls back to `http://localhost:3000/` for both deployed origin forms. The production origin and confirmation return must be configured in Supabase Auth's Site URL/redirect allowlist. The connected management tools do not expose that mutation. Confirmation, RLS and provider security remain enabled; the app does not send users to the Supabase developer dashboard.

Apple sign-in remains hidden until its provider is configured. The existing leaked-password-protection warning remains an operator Auth setting. See [the executed preservation audit](reports/v7-database-preservation.json) and [the account architecture](AUTH_V5.md).
