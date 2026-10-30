# Database continuity and migration recovery

This guide covers the preserved **legacy SQLite workspace** and its recovery procedures. GRIDIRON AI also supports a separately selected Supabase PostgreSQL/Auth/RLS backend; see [SUPABASE.md](SUPABASE.md) and [DEPLOYMENT.md](DEPLOYMENT.md) for its versioned migrations, reviewed account import and project-level restore boundaries. Selecting Supabase does not delete or migrate SQLite records automatically.

The legacy workspace uses `DATA_DIR/gridiron.sqlite`. Run a single application instance against that volume. Container restarts preserve those local records only when the same persistent directory is mounted. A fresh filesystem or a new empty DATA_DIR is a different database, not a migration. Supabase account records instead remain in the configured remote project across Node restarts/redeployments.

The legacy application enforces account ownership in each database operation. SQLite does not offer PostgreSQL row-level security; this statement does not apply to the Supabase mode, which has database-native RLS. Keep direct database access limited to trusted operators. Sessions are stored as token digests and survive process restarts until expiration or sign-out. Password hashes use scrypt. SQLite and its automatic migration snapshots are not application-encrypted; protect the storage volume and backups with host/disk encryption and access controls.

## Before a 2.0 upgrade

1. Identify the existing volume and database. Keep the previous source/container image and environment configuration. Do not initialize a different directory to make an upgrade error disappear.
2. Produce a consistent snapshot **before** starting the new application. With the previous database mounted, run from the project directory:

   ```sh
   DATA_DIR=/your/persistent/data node --import tsx scripts/backup-database.ts
   ```

   This maintenance command opens an existing database without invoking the application migration runner. If no database exists, it reports that and changes nothing. The command uses `VACUUM INTO`, which captures committed write-ahead-log contents. Copying only an open `.sqlite` file can omit committed WAL transactions.

3. Store a snapshot off-host using a secure encrypted backup destination. Raw SQLite snapshots contain account data and authentication hashes; restrict access. Test that a copy opens with `PRAGMA integrity_check` returning `ok`.
4. Confirm that the previous deployment can authenticate and read the same known records before replacing it. Record transaction counts, available balances, pending exposure, and selected historical IDs. Never print credentials, session tokens, or private records into deployment logs.
5. Start the new application with the same volume. Its first database access verifies migration history and takes another consistent snapshot before making any pending schema changes to an existing database. Snapshots are written under `DATA_DIR/backups/` with unique names and file mode `0600`. New backup directories are created with mode `0700`; protect existing parent-directory permissions separately.

An empty initial installation has no previous database to back up. A migration of a legacy v1 database is supported: the unchanged, idempotent `001_initial.sql` is recorded and the additive `002_quant.sql` introduces research/history tables. The migration never resets balances or recreates account records. No automatic downgrade or data reset is attempted.

## Migration rules

Migration files are ordered by their three-digit filename prefix. The database records each filename, SHA-256 checksum, and application time in `schema_migrations`. Already-applied SQL is immutable. A missing or changed applied file aborts startup; restore the original file and add a new migration instead of rewriting history.

Each pending file runs in its own immediate transaction. An error rolls back that file and leaves earlier successful files recorded. The application closes the failed connection and reports the failure; it does not delete the database or continue with a replacement dataset. A failed, unapplied file may be repaired after inspecting the actual error. Retain the pre-upgrade snapshot until verification is complete.

The research warehouse uses append-only quotes, prediction snapshots, contract settlements, injury history, and warehouse records. Database triggers reject updates to those historical rows. Account deletion still cascades through owned records; immutable history does not defeat a user's deletion request.

## Recovery

1. Stop all application instances before restoring. Keep the failing database, its `-wal`/`-shm` files, logs, source version, and snapshot paths for diagnosis. Do not overwrite the only copy.
2. Verify a copy of the pre-upgrade snapshot with SQLite's `PRAGMA integrity_check`. Confirm its expected schema and record counts.
3. Restore a verified snapshot into a **separate** persistent directory and start the previous matching application version against it. Restore permissions and secrets through the deployment platform. Verify authentication and known ledger balances before switching traffic.
4. Reconcile records written after the snapshot before adopting the restored instance. A restore cannot automatically preserve later writes. Keep both copies until that reconciliation is complete.
5. Repair forward with an additional migration after identifying the cause. Do not remove migration-history rows or run a destructive “down” script to force the new application to start.

Automatic local snapshots are recovery aids, not an off-site disaster-recovery service. Operators must choose retention, encryption, off-host storage, and restore drills.

## Encrypted account export

Bankroll's backup export encrypts account-owned ledger, research/history records, conversations, and preferences using AES-256-GCM with a scrypt-derived key, a fresh 16-byte salt, and a fresh 12-byte nonce. Passwords and active session tokens are excluded from this account export. The encrypted envelope remains compatible with `scripts/decrypt-backup.mjs`. Keep the password separately; authentication fails if the password or ciphertext is wrong.

An encrypted account export is not a complete SQLite snapshot and cannot restore sign-in sessions. The current application does not automatically import a whole backup as database state. Use verified transaction imports for supported ledger rows and retain decrypted research exports for review or a deliberate recovery workflow.

## Verification commands

```sh
npx vitest run tests/ledger.test.ts tests/auth.test.ts tests/persistence.test.ts tests/backups.test.ts
```

The persistence suite uses separate Node processes and temporary databases to test restart continuity, session ownership, historical records, migration preservation, WAL snapshots, checksum rejection, and failed-migration rollback. The cryptographic suite tests encrypted-export recovery and tamper/wrong-password rejection. Consult the delivery report for actual results from the current environment; this command is not itself evidence that a deployment has passed.
