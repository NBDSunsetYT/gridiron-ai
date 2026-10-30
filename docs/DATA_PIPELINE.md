# Owner-scoped research scheduling

The pipeline is disabled by default. In Settings, choose a 5-, 15- or 60-minute minimum interval and explicitly enable the public schedule adapter, licensed odds adapter, owned injury queue and/or model auditor. Preferences and timestamped run summaries are saved in the authenticated database. Every source step records completion, unchanged evidence, failure or unavailable access. Enabling an absent licensed feed never creates substitute news or prices.

The browser component checks due work once per minute **while the page is open and visible**. Browser background throttling, closing the app and device sleep stop this mechanism. The server enforces the configured interval and a one-minute minimum cooldown even for an explicit Run now. The process suppresses concurrent runs for the same owner. For horizontally scaled deployment, supply the optional storage `claimRun` implementation using an atomic owner-scoped database claim; a process-local lock alone does not provide a global distributed lease.

Injury processing reads the actual saved injury evidence and job queue. It requests simulations only for already queued owned jobs. Unsupported cohorts remain blocked by the simulation engine. Source fingerprints do not turn a refreshed timestamp into a statistical feature change. No model is automatically promoted and no new prediction is manufactured to fill missing coverage.

## Closed-app operator scheduling

An operator can invoke `node scripts/research-pipeline.mjs` from a supervised scheduler. Configure the actual HTTPS `APP_URL` and your own authenticated cookie in `GRIDIRON_PIPELINE_OWNER_COOKIE` or a private file named by `GRIDIRON_PIPELINE_COOKIE_FILE`. Never put cookies in command arguments, source, scheduler logs or a public URL. Cookie files are rewritten with mode 0600 when the server refreshes a session. Retain the backend-selection cookie along with your signed-in session.

The script does not accept a shared cron secret as permission to read arbitrary users. Authentication expires normally; a rejected session requires the operator to sign in again. It does not provision an external scheduler, APNs delivery, a paid feed or a user-wide privileged service role. Use the hosting platform's secure environment facilities, retention rules and monitoring.

The public warehouse adapter and its provenance boundaries are documented separately by the warehouse implementation. Historical event timestamps do not prove when data became available for forecasting.

## Actual NFL history import

`GET /api/warehouse?kind=games|teams|players|plays|team_statistics|player_statistics&q=...&limit=300` reads only the signed-in account. `POST /api/warehouse` with `{ "action": "sync_games", "seasonFrom": 2023, "seasonTo": 2025 }` imports the fixed public nflverse schedule source, bounded to six seasons. It stores actual recorded games, team abbreviations, and identified starting quarterbacks. It does not invent player game logs, routes, snap counts, injuries or weather.

The nflreadr schedule dictionary explicitly defines `gametime` as Eastern time even for international games. Conversion uses `America/New_York` with DST. Missing or invalid kickoff timestamps are excluded rather than assigned a guessed noon/midnight time. Both observed scores must exist before a game is labeled completed.

Each retained source snapshot includes source URL, collection time, event time, availability (null when unknown), SHA-256 version, and reliability status. A file fetched today does not prove historical publication availability. Strict point-in-time modeling must not treat these records as historically available without additional evidence.

SQLite retains immutable source snapshots and deterministic receipt IDs. Supabase writes typed owner-scoped `nfl_seasons`, `nfl_teams`, `nfl_players`, and `nfl_games`, with immutable version snapshots under `gridiron_records`. An exact file/range retry returns its existing receipt. Cloud imports use bounded retryable batches: a failed batch can leave typed source views partially populated, but the receipt is saved only after completion, and retries use deterministic IDs. Existing financial records are never modified by a warehouse import.

The API currently supports the public schedule source only. Detailed play/statistical imports remain unavailable through this endpoint; the separate modeling CSV adapter supports explicitly supplied historical plays. The warehouse screen reports absent play/usage coverage instead of synthesizing those records.
