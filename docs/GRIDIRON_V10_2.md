# GRIDIRON AI 10.2 and shared research storage repair

The existing Next.js PWA, Vercel private Python engine, Render data gateway, Supabase project and auditable Wallet are preserved. No existing user rows are reset or rewritten.

## Storage diagnosis and repair

`POST /api/nfl/games/2026_08_BAL_BUF/analyze` returned HTTP 503 with the generic shared-storage message. Supabase was reachable. The required tables, RLS and API grants existed. PostgreSQL's application admission guard rejects new `job_enqueue`/`job_complete` operations with SQLSTATE 54000 above 450,000,000 database bytes; the database measured 451,843,763 bytes. This was not a missing-table or personal sign-in error. Hundreds of MB are archived public market quotes and immutable snapshots.

New shared NFL job contexts and completed payloads are compressed, content-addressed and stored without overwrite in the private Supabase Storage bucket `gridiron-shared-research-v1`. Existing job/snapshot tables retain compact searchable summaries and SHA256 references. Readers support both original inline records and new objects, checking compressed and decoded hashes. Publication is complete only after both object storage and PostgreSQL acknowledge it. Failed metadata writes can leave a harmless immutable orphan object, never a false Saved status.

The bulk market-ingestion ceiling remains 450 MB. A separate bounded operational reserve permits NFL job metadata of at most 64 KiB until 470 MB, retaining at least 30 MB below the existing 500 MB free database limit for account records. No subscription or paid-resource change was made. This reserve is finite; monitor usage. No historical record was deleted to make room.

The Edge Function uses the project's server-side secret environment and validates the existing backend ingestion capability through a service-role-only authorization RPC. It does not accept app-user JWTs as elevated authorization. The bucket is private; no browser or anonymous storage policies were added. Service-role credentials never reach Next.js client code. The caller cannot choose an external storage URL. The function rejects payload keys containing credentials or account balances.

`POST /api/nfl/storage-check` accepts no user data and runs a bounded isolated public operational canary: immutable object write/read, existing cache-table write/read/update/retrieval and preservation of the original object. It never changes a user workspace, financial record, prediction or authentication account. `GET` reads the persisted canary after refresh/reopen. Rate limiting protects this endpoint. This test does not establish authenticated private-account acceptance.

Errors distinguish authentication, database permission, schema mismatch, network timeout, backend outage, capacity and temporary service failures without returning raw SQL or credentials. Signed-in research drafts use encrypted account-scoped IndexedDB recovery and revision-aware, idempotent cloud sync; guest drafts use session storage. Existing cloud versions are authoritative and conflicting edits remain recoverable. Private data is never placed in service-worker caches.

## Probability to hit

NFL/CFB props, exact stored event-contract research, game winner/margin/total controls and combinations have probability actions. Only server-retrieved data and reconciled complete-game histograms generate hit counts. Supported modes are 10,000/50,000/100,000 complete games. Raw estimates, calibration evidence, Monte Carlo standard error and sampling intervals remain distinct from model/scenario uncertainty. No approved calibration artifact means calibrated probability stays unavailable.

In-game predictions are withheld: fresh complete live-state features and an independently validated live model are not configured. Pregame estimates cannot become live probabilities by relabeling a scoreboard.

Private probability observations are append-only, owner-scoped and HMAC-attested, with immutable history and export. Quote changes are separate from independent model evidence. Unsupported inputs remain unavailable. Source checks and automatic input invalidation continue through the existing pipeline; no claim of complete injury/weather modeling is made.

## One-tap parlay research

Prop cards toggle + Add to Parlay / ✓ Added without confirmation. A persistent floating slip supports removal, undo, cloud saves, reopen, rename, duplicate, recoverable archive, restoration, history, JSON/CSV export and Wallet handoff. Restoring creates a version. Archiving research never deletes an actual wager.

Same-game statistical thresholds can be evaluated together by the existing NFL/NCAA engines. Joint probabilities use aligned complete-game outcomes. Cross-game dependence and incompatible exact contract definitions are withheld rather than filled with multiplied marginals.

Multiplied sportsbook odds are explicitly theoretical and never a verified same-game offer. Separate event contracts never imply a sportsbook parlay payout. Manual multiplier/fees use Decimal arithmetic. Record My Wager opens the existing explicit Wallet confirmation; actual accepted odds must be entered. Research never posts a transaction automatically.

## Limits and recovery

DraftKings Predictions live access is still not authorized. PropLine supplies sportsbook reference lines and is labeled accordingly. Current injuries, availability and fitted weather effects remain incomplete; uncertain player restrictions withhold unsupported prop probabilities. No market superiority or guaranteed outcome is claimed. OpenAI generation requires valid provider credentials/entitlement; saved evidence tools do not invent an AI response.

Retrospective CFB audits have small samples and unknown historical publication availability. They do not approve calibration or promote a model. See the recorded audit and test reports.

For recovery, preserve both the PostgreSQL metadata/history and the private bucket objects; a database backup alone cannot restore newly offloaded payloads. Do not remove referenced objects. Old inline records remain readable. Code rollback must retain the object reader; reverting to a pre-object version alone would make new payloads inaccessible to that version. Database admission changes are reversible via the guarded function clause documented in the migration, without deleting rows.

Production authenticated cross-device private-account tests require an isolated verified app identity. Physical iPhone installation must be tested on the device; WebKit mobile emulation does not establish physical installation.

## Verified release evidence

The storage diagnosis was reproduced on the original game-analysis request. The deployed repair passed actual object/database write, read, update and retrieval checks with an isolated operational record, including preservation of its original payload. A real 10,000-game NFL result reopened from durable storage. The fixed probability action returned its actual hit counts, and same-game joint research evaluated 10,000 aligned games rather than multiplying individual probabilities. Raw probabilities remain uncalibrated. See [full verification scope](reports/v10-2-verification.json), [production storage evidence](reports/v10-2-production-storage.json), [production PWA checks](reports/v10-2-production-pwa.json) and [production browser checks](reports/v10-2-production-browser.json).

The final application source commit is `bb18d82ae756ca68f80b50a17a40ffff190940cf`; the deployed source manifest is recorded in the production evidence. Later documentation commits do not change that runtime source. The workspace's outbound HTTP tunnel subsequently failed for all destinations; final production requests were verified through the connected Supabase and Vercel services instead. Browser/PWA production reports identify the earlier storage deployment on which those checks ran. No physical iPhone installation or authenticated cross-device private-account write test is claimed.

Draft loading waits for the app identity and recovered data before accepting edits. Legacy 10.0 device drafts remain readable and are retained during migration. Transient pending research saves retry while the app is visible, using the same mutation identity. Conflicting cloud revisions cannot be silently overwritten. Switching sports resets research state while preserving the Wallet view and its complete account totals.

Joint research compares immutable fitted-byte provenance and the statistical feature fingerprint separately. Collection clocks can change fitted bytes without changing verified football inputs. Model version, sport, teams, kickoff, fitting date and semantic availability/roster inputs must agree; current joint marginals come from the joint run itself. Unsupported or changed evidence is withheld. Earlier predictions and their original byte hashes are preserved.

For source-based deployment, apply the versioned migrations and deploy `supabase/functions/shared-research-store/index.ts` as `shared-research-store` in the existing project. Its platform JWT check is disabled because the function performs its own mandatory server-capability authentication. Never remove that authentication or expose its secret. Supabase supplies the function's server-only project credentials; no service-role key belongs in a browser. Preserve the private bucket and its objects alongside database recovery archives.

The Supabase security advisor also reported existing disabled password-breach screening. It was not the storage failure and no paid plan was enabled. [Supabase password-security guidance](https://supabase.com/docs/guides/auth/password-security#password-strength-and-leaked-password-protection) describes that separate setting. The private recovery-checkpoint table intentionally has no client-access policy.

The optional encrypted offline-history controls now wait for the app identity before mounting. A delayed authentication response can no longer reset a passphrase entered into the prior guest view. The regression reproduces a delayed identity response and verifies encryption, offline recovery and rejection of an incorrect passphrase.
