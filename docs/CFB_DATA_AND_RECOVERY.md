# NFL and college-football data protection

The existing Supabase project `qdtdjbapdipopncklsdb` is reused. Migration `20261031183047_gridiron_v8_football.sql` adds separate college-football source identities, relational warehouse families, provider-reference quotes, private simulation/prediction metadata, and nullable wager sport metadata. Existing wager amounts, notes, prediction JSON and records are preserved. Existing wagers with unknown sport remain **Unspecified**.

The production migration was preceded by a fresh encrypted private-data checkpoint. All 49 original private/Auth table-family counts and content digests matched before and after the migration; both real accounts remained intact. The checkpoint was decrypted and its counts reconciled locally. Its key and ciphertext are stored outside the repository with restrictive permissions; the key is never included in source ZIPs or browser code. This checkpoint excludes the large shared public research archive and is not a verified full-project, Storage or managed point-in-time backup. The JSON verification report records the exact scope.

## Security boundaries

All 73 public-schema tables have row-level security. Shared college schedules, source versions and reference quotes have deliberate public read policies. Private college runs and snapshots require the authenticated owner. Existing owner-scoped `gridiron_records` stores the complete generated college result and saved research. The server attests both numeric output and its game/player/source context; edited or imported evidence is withheld when its proof cannot be verified.

Public write functions require the existing server-only ingestion capability. They reject private financial fields and credentials from shared JSON. NFL and CFB identifiers are distinct. BALLDONTLIE and CollegeFootballData traditional sportsbook-reference quotes cannot be stored as DraftKings Predictions contracts. Separate contract thresholds, prices and settlement conditions must be independently verified.

Provider API keys are read only by the private Render gateway. Vercel needs only the private bridge URL/token. The CFB simulation service uses the existing private simulation URL/token and never exposes its signed model or service secret in the browser. Supabase service-role credentials are not used by client code.

## Existing storage limit

The database currently exceeds the existing 450,000,000-byte public-data admission threshold. The upgrade preserves that guard. New shared sources, quotes, warehouse rows and cache writes remain paused to protect personal records. No historical research was deleted, no free capacity was manufactured and no paid plan was enabled.

Guest schedules and simulations can use bounded server memory and must be labeled temporary. They do not provide durable history across cold starts or deployments. Signed-in users can save actual generated evidence in their own existing persistent record store. Typed CFB owner tables are prepared and included in account exports; the complete result remains in `gridiron_records`.

CFB compute reservations contain only an input hash, simulation count, UTC day and fenced execution status. They use the same existing 500,000-complete-game daily budget and admission lock as NFL jobs. Counts are never reset, decremented or refunded by retries. A completed guest reservation whose temporary result has been lost is not rerun without a new charged reservation. Shared persistence remains blocked even though tiny control metadata and legitimate private records are permitted.

## Sources and statistical limits

The guest schedule comes from ESPN's published college-football scoreboard, preserving canonical ESPN event/team identities, actual kickoff verification, status, score, ranks where provided, source URL and collection time. Unknown conference names, classifications, injuries and depth charts remain missing. Source sportsbook odds and vendor model percentages are not imported as independent forecasts.

The separate NCAA baseline fits actual identified SportsDataverse college play-by-play. Current transfers, rosters, official injuries, snap restrictions and numerical weather adjustments are not fully verified; projections are explicitly conditional on historical modeled opportunities. Incomplete source receiver identification does not establish complete target shares. Monte Carlo sampling error is separate from model uncertainty. The weak four-game retrospective pilot is not prospective validation and did not promote a calibrated model. Missing contracts do not prevent displaying actual independent player distributions, but those distributions have no invented line, market price, calibrated probability or expected value.

## Recovery and rollback

Before future schema changes, capture a consistent encrypted checkpoint of owner-scoped tables (identify tables by their `user_id` ownership column, not by a broad public-schema dump), plus the selected Auth tables, and verify decryption and row counts. Shared research and binary Storage require separate appropriately sized backups. Keep recovery keys separate from encrypted archives and test restoration in an isolated project before changing production.

Account exports include complete owned generic records, conversations, financial data and typed CFB metadata. Generated proofs depend on the stable simulation service secret; preserve that secret securely across deployments. Moving evidence to a different owner without rerunning/re-attesting it does not establish generated provenance. Typed warehouse restoration remains archived in the imported source payload until its dedicated typed restore is implemented; a consistent project-level restore is required for complete relational recovery.

Rollback this additive release by restoring the previous application build while retaining the nullable wager `sport` column and all new records. Do not drop populated tables or strip sport metadata. Revert a function only from a reviewed prior definition and verify the original RLS/capability checks and financial arithmetic. Supabase Auth Site URL/redirect allow-list and leaked-password protection remain provider account settings; do not disable email confirmation or change user rows to work around missing administrative authorization.
