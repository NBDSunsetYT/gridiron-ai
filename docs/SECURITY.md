# Security and privacy

## 4.0 cloud and native boundaries

Cloud mode uses configured Supabase Auth, verified owner JWTs, HTTP-only cookies, RLS enabled on all 47 public tables and authenticated atomic financial RPCs. Legacy SQLite authentication/storage remains a separate explicit workspace. Cloud outages do not silently use local records. See [SUPABASE.md](SUPABASE.md) for remote account deletion, session revocation and migration details, and [AUDIT_V4.md](AUDIT_V4.md) for actual remote checks.

The final advisor reported no SQL/RLS finding and one warning: leaked-password protection is disabled. Enable the optional Auth dashboard setting if supported by the plan. Logical encrypted exports are verified; provider backup/PITR configuration and retention are not verified. Complete typed archives are included, but full normalized-table restore reconstruction remains incomplete.

The native source keeps approved session cookies in device-only Keychain storage and does not return credentials to JavaScript. This source/preparation behavior is tested separately from device behavior; no Xcode compilation, native Keychain execution, APNs delivery or signed IPA was verified on Linux. Read [NATIVE_IPHONE.md](NATIVE_IPHONE.md).

## Legacy deployment boundary

Use HTTPS and a private deployment for personal financial data. This application uses email/password accounts, password hashing, opaque server-side sessions, HTTP-only cookies, same-origin checks on mutations, rate limits, and user-scoped queries. These controls reduce common risks; they do not replace a security review or host maintenance. Never share the persistent database publicly.

The SQLite database contains personal ledger, wager, account, and market records. Volume-level or disk encryption is the operator's responsibility. Secure the database, WAL/SHM files, backups, exports, logs, and environment equally. Provider keys are server configuration and are never intentionally shipped to the browser.

## Browser storage and offline behavior

The service worker caches only public installation assets and static application bundles. Authenticated HTML and all `/api/` requests bypass caching. An explicit Settings action can save a separate encrypted historical ledger snapshot in device localStorage: AES-256-GCM, fresh 16-byte salt/12-byte nonce, PBKDF2-SHA256 with 310,000 iterations, no stored passphrase/key. This snapshot is opt-in, device-specific, read-only and potentially stale. Its key is separate from server backup encryption. Account deletion clears it on the current device; other devices and exported files must be managed separately. Preferences may also be stored locally. CSVs are unencrypted. Losing an archive/snapshot passphrase prevents recovery.

Signing out removes the active server session. Device operating-system security is separate. Biometric unlock and WebAuthn are not implemented in this release; use a strong device passcode and the browser's established account-security tools.

## AI data handling

When enabled, GRIDIRON INTELLIGENCE sends your prompt and selected context/tool results to the configured OpenAI service. It may query your user-scoped financial records to answer an explicitly financial question. Do not put API keys, passwords, confidential third-party data, or information you do not want processed by the provider into prompts. Review OpenAI's current data-processing terms before enabling it for sensitive records.

The model can explain existing evidence and calculations. A text answer is not evidence that a feed was queried; source timestamps and structured tool results are the evidence. Missing sources must remain explicit. The assistant cannot place a wager.

## Data controls

Use CSV export for review and backups for portability. Inspect account deletion and backup behavior on a disposable account first. Retention policies for exported files, reverse-proxy logs, provider logs, and off-host backups are the operator's responsibility. Removing an account from this database cannot recall files you have already downloaded.

## Responsible use

This software records and analyzes research. It does not automate betting. Limits are personal recordkeeping controls rather than sportsbook-enforced limits. For enforceable deposit limits or self-exclusion, configure the relevant licensed sportsbook's own account controls. Probability estimates carry sampling and model uncertainty; they never establish guaranteed returns.

## Recover an encrypted ledger archive

The backup action produces AES-256-GCM ciphertext with a scrypt-derived key, random salt, and random IV. Keep the passphrase separately. The archive includes ledger reports, raw owner-scoped financial postings/audit, settings/preferences, research, conversation history, simulation outputs and replay inputs. It is not a byte-for-byte SQLite backup and excludes provider secrets, password hashes and sessions. The cloud migration/import UI restores finances and compatible app histories and retains the full typed archive, but does not reconstruct every normalized NFL/model table. No complete normalized restore is claimed. Use a consistent SQLite snapshot or a verified project-level PostgreSQL restore for full disaster recovery.

To inspect a recovered archive, write the passphrase to the utility's stdin using a trusted password manager or shell prompt, then run:

```sh
node scripts/decrypt-backup.mjs gridiron-backup.encrypted.json recovered.json
```

The utility reads the passphrase from stdin until EOF (Ctrl-D on Unix). Terminal input may be visible; use your shell's hidden-input facility when entering a real passphrase. Do not put the passphrase in command arguments or commit password files. Successful recovery writes `recovered.json` with mode 0600 and refuses to overwrite an existing file. The output is unencrypted sensitive data. Inspect it locally and delete it securely when no longer needed. Re-importing ledger rows requires careful reconciliation; do not replay settlements or returned stakes as fresh deposits.
