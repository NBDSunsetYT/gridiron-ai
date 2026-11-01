# GRIDIRON AI 11.0 storage upgrade

The existing app, Vercel services, Render data gateway, Supabase Auth, exact financial ledger, research history and iPhone PWA are preserved. No pre-existing record is migrated, overwritten or deleted by this release.

## Record ownership

| System | Responsibility | Release status |
|---|---|---|
| Supabase `qdtdjbapdipopncklsdb` | Authentication, profiles, ledger, deposits, withdrawals, wagers, settlements, combinations, preferences, AI conversations, saved references and small coordination records | Existing production integration retained. New coordinator migration verified. |
| MongoDB Atlas | Public NFL/CFB simulation aggregates, source metadata, injury snapshots, matchup reports and explanations | Driver, bounded document schema, immutable writes, pagination and outbox implemented. Actual Atlas activation blocked by organization AI-client policy and missing application credentials. |
| Private Cloudflare R2 | Optional exact fitted artifacts, compressed datasets and explicitly requested aggregate run archives | Server-side adapter and verified upload/download paths implemented. Actual R2 access is not configured or tested in this account. No bucket was created. |
| Existing private Supabase object bucket | Backward-compatible research payloads and durable external-delivery staging | Retained as the verified recovery path while external services are unavailable. |

The deployed Python engine currently runs as the existing private Vercel service. Render remains the existing authorized data gateway. This release does not relocate either service or purchase infrastructure.

## Compact runs and reproducibility

Both NFL and NCAA engines already streamed completed games into histograms. This release adds a storage boundary rejecting full-game arrays, raw samples and play collections in ordinary permanent research documents. At most three representative games, each bounded to 1,000 inspection plays, can be retained. The engines default to zero representatives; automatic game research requests one. Parameter-uncertainty replicates are also saved as marginal player frequencies and joint score-pair frequencies, rather than ordered game/statistic frames. Single-threshold intervals retain the original weighted counts; player marginals are never treated as paired joint outcomes. Both legacy ordered encodings remain readable. An explicit cross-language test verifies unchanged intervals, including tie settlement semantics.

The 10,000, 50,000 and 100,000 modes mean complete games. The six mechanical mode tests reconcile every score histogram and shared contract outcome count, assert bounded serialized output and verify that full sample arrays are absent. Those fixtures are visibly synthetic mechanics tests, not historical calibration evidence.

New run manifests retain seed, configuration, model/input fingerprints, fitting parameters, scenario assumptions, feature references, engine/code-file hashes, Python/runtime details and dependency versions. They distinguish a deterministic replay key from the execution's existing simulation/job ID. User ownership remains in Supabase, not in shared MongoDB documents. Historical runs lacking manifests are not retroactively assigned invented versions or dependencies.

Quarterback/receiver and team-score correlations use bounded streaming cross moments over the same complete games. These summaries retain no per-game sample array. Sampling intervals and Monte Carlo errors remain separate from model/scenario uncertainty. No calibration or forecasting improvement is claimed by a storage upgrade.

`GRIDIRON_ARCHIVE_MODEL_ARTIFACTS=1` opts the automatic research worker into archiving the exact fitted input bytes through an authenticated server-only gateway. A receipt must match the original bytes before the manifest calls that archive verified. The gateway rejects financial payloads, checks compressed/expanded bounds and requires a private bucket. It does not forward service credentials on redirects.

Without an archived fitted artifact, a seed/version label alone is insufficient for exact replay. Manifests explicitly report that limitation. With a verified artifact, replay still requires matching code, configuration, dependency/runtime behavior and any saved postprocessing evidence. Wall-clock timestamps, durations and archival receipts are outside deterministic statistical replay. Actual R2-backed replay has not been tested without account access.

## Delivery and integrity

1. Write and verify a compressed immutable staging object.
2. Save only its reference and bounded document metadata in the Supabase outbox.
3. Claim delivery with a fenced lease and send an idempotent MongoDB upsert.
4. Read back and verify canonical content before acknowledging delivery.
5. Retry failures with backoff; exhausted/crashed workers become visible dead-letter jobs.

These operations are not a cross-database transaction. A failed metadata write can leave a harmless immutable object; it cannot produce a false external-delivery acknowledgment. Unavailable external research falls back to the verified staging object. Detected MongoDB checksum mismatches create redacted integrity alerts. Existing legacy inline records and version-one object pointers remain readable.

Documents use canonical byte identities, including numeric-looking JSON property names. MongoDB `_id` provides deduplication, and a compound sport/game/time/ID index supports cursor pagination. A single client per warm serverless instance uses a small pool. New collections receive validation; existing unknown schemas are not rewritten. Research collections have no TTL deletion.

New NFL and CFB private saves retain a small account-scoped reference (NFL references also pin the exact original result checksum; CFB retains its owner-bound attestations). Retrieval materializes the research and verifies both result and source context. Encrypted account exports expand those references into complete research evidence so the backup does not silently omit the data. Old inline saved records remain compatible.

Exact-byte dataset/artifact deduplication uses content-addressed keys and conditional R2 writes. It does not collapse immutable prediction snapshots or claim semantically similar datasets are byte-identical. Durable staging duplication is a recovery mechanism; it is not an assertion that two databases commit atomically.

The existing signed NFL refresh schedule also drains configured research deliveries. New NFL completions and CFB saves attempt a small bounded delivery. The optional `POST /api/internal/storage/sync` supports the existing scheduler credential or an authorized app administrator. No extra paid cron service was provisioned.

## Internal monitoring and privacy

Advanced Mode → Settings includes Storage health. Its API requires a verified app identity whose ID is in `GRIDIRON_STORAGE_ADMIN_USER_IDS`, or a trusted Supabase `app_metadata.gridiron_storage_admin` flag. User-editable `user_metadata` cannot grant access. No administrator was guessed from the two existing accounts; the app sign-in email is required to identify the owner's account safely.

The panel reports actual Supabase database/object usage, MongoDB database statistics when reachable, registered R2 bytes, simulation archive bytes, delivery states, integrity alerts and verified backup status. R2 catalog bytes exclude other bucket/account objects. Cost estimates remain unavailable unless a unit price is configured; they exclude operations, taxes and account-wide free allowances. They are not billing statements.

The current configured Supabase free database limit is 500 MB. Existing bulk archival admission remains bounded at 450 MB; lightweight operational metadata remains bounded at 470 MB. Nothing was deleted to reduce the measured database size. MongoDB/R2 warning limits are explicit optional budgets, not assumed provider tiers.

R2 uploads require S3 credentials and Cloudflare account read authorization to verify that both managed `r2.dev` access and custom public domains are disabled. Privacy is rechecked before uploads. There are no public bucket policies, browser credentials or automatic presigned download URLs. Private financial records and AI conversations never enter MongoDB/R2.

## Retention and recovery

Irreversible cleanup is **preview only**. Eligibility requires an expired disposable kind, no protection/reference and a verified matching backup. Financial records, combinations, prediction history, model evaluations, saved research and required audit records are never eligible. No production database or bucket purge was scheduled.

The current engines do not create full-run play files. Existing source-download temporary files and cache expiration behavior remain in place. Cleanup of archived staging, historical datasets and failed operational metadata is withheld until backup/restore receipts and reference checks are available. No automated backup receipt is fabricated from a successful upload.

Restore requires the Supabase metadata and original private object bucket, plus any activated MongoDB documents and R2 objects. Preserve stable server attestation secrets securely. The pre-release private-data checkpoint was AES-256-GCM encrypted and round-trip verified outside the source repository; authentication secrets were excluded. A database-only backup is insufficient to recover externally stored research. No full multi-provider restore has been verified yet.

Rollback must retain the new pointer reader and CFB hydration/export support for records saved after this release. Disable external routing first; do not drop the outbox, archive catalog, integrity alerts or staging objects. The migration creates only new operational tables/functions and changes no old table contents.

## Activation requirements and observed blockers

Atlas MCP returned: **AI client access is disabled for every organization on the connected account (two organizations)**. Its response says retrying or reauthentication will not fix that policy. An Organization Owner must enable AI client access before authorized inspection/configuration can continue. There is also no deployed `MONGODB_URI`. No project, cluster, database user or network allow-all rule was created.

Cloudflare/R2 management tools are not available in this session; plugin discovery returned no available R2 connection. No R2 credentials are configured on the app. An authorized account connection or securely configured server credentials are required. Do not paste secrets into GitHub or chat.

Set the following only in the existing production server's encrypted environment configuration, after authorized project/bucket inspection:

```text
GRIDIRON_MONGODB_RESEARCH=0
MONGODB_URI=
MONGODB_DATABASE=gridiron_research
R2_ACCOUNT_ID=
R2_BUCKET=
R2_ACCESS_KEY_ID=
R2_SECRET_ACCESS_KEY=
CLOUDFLARE_R2_ADMIN_TOKEN=
GRIDIRON_ARCHIVE_MODEL_ARTIFACTS=0
GRIDIRON_STORAGE_ADMIN_USER_IDS=
```

Keep both opt-in flags disabled until actual cloud read/write/retrieval tests pass. Use a dedicated Atlas research database, a least-privileged database user, verified TLS and an approved hosting-egress allowlist. Do not open all network addresses automatically. Scope R2 object credentials to the intended private bucket and the account token to the necessary read-only privacy inspection.

Optional monitoring values are `MONGODB_STORAGE_LIMIT_BYTES`, `R2_STORAGE_WARNING_BYTES`, `MONGODB_STORAGE_USD_PER_GB_MONTH` and `R2_STORAGE_USD_PER_GB_MONTH`. Blank limits/prices mean unknown, not zero cost.

`POST /api/internal/storage/archives` accepts a selected NFL run or the administrator's own saved CFB run and an explicit archive request. It archives aggregate distributions and representative games. Full play-by-play run archiving is not implemented; this release intentionally does not collect all generated plays. Actual R2 archival remains unavailable until authorized configuration is verified.

## Verification scope

See the release's machine-readable verification report. Local MongoDB tests use a real isolated MongoDB engine with synthetic documents; they do not establish Atlas account access. R2 transport/privacy/integrity tests exercise controlled responses, not the user's cloud bucket. Production Supabase coordinator operations were tested using a rolled-back isolated record, with no financial write or false claim of MongoDB delivery. All 93 pre-upgrade NFL snapshots retained their exact checksum after migration.

The existing source, app routes and PWA installation instructions remain available. See [iPhone installation](IPHONE.md) and [the prior storage recovery notes](GRIDIRON_V10_2.md).
