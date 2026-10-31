# GRIDIRON AI9.0 — PropLine operational scope

The existing application is upgraded in place. PropLine is the primary NFL/CFB sportsbook-prop source. DraftKings Predictions remains a separate, unconfigured event-contract feed. Legacy BALLDONTLIE routes remain for compatibility but no longer power the default player-prop interface, scheduled source refreshes or research tools.

## Verified provider access

Official reference: https://prop-line.com/docs and https://prop-line.com/llms-full.txt.

The operator-owned credential was configured using Render's environment-variable API on the explicitly free `gridiron-propline-gateway` service. The credential never enters Vercel, source, client bundles or temporary configuration files. Vercel receives only the Render URL and a separate internal bridge credential. Health checks and unauthenticated callers cannot read provider keys. No paid Render tier or new provider subscription was activated.

Actual authenticated requests from Render returned HTTP200. Provider headers identify a5,000requests/day Hobby quota. Exact live inventory changes continuously. A retained sample had:

| Sport | Valid current outcome rows | DraftKings Sportsbook | FanDuel | BetMGM | Hard Rock |
|---|---:|---:|---:|---:|---:|
| NFL |14,140|1,477|1,210|1,137|10,316|
| CFB |1,063|341|373|94|255|

NFL nonempty categories: passing yards, passing touchdowns, passing attempts, passing completions, interceptions thrown, rushing yards, rushing attempts, receiving yards, receptions, anytime touchdowns. CFB nonempty categories: passing yards, passing touchdowns, passing attempts, passing completions, rushing yards, receiving yards, receptions, anytime touchdowns. Separate rushing-/receiving-touchdown markets were requested but absent from this sample. This is observed inventory, not a promise about future availability.

Endpoints actually used: `GET /v1/sports/football_nfl/odds`, `GET /v1/sports/football_ncaaf/odds`, and each sport's documented `/ids` crosswalk. Authentication is the `X-API-Key` header. Queries explicitly request supported market keys and selected traditional sportsbooks; exchange and DFS rows are excluded. Event identities join on provider crosswalk IDs and exact kickoff, not fuzzy team names. Missing player IDs are not guessed.

## Data and modeling boundaries

The gateway caches bounded boards, prioritizes DraftKings Sportsbook and serves500-row pages with total counts. It respects Retry-After and daily-reset headers, distinguishes burst vs daily throttling, and never follows provider redirects with credentials. Local counters are conservative; provider quota headers remain authoritative across worker restarts. The server and UI reject/withhold stale rows and retain original provider-observation timestamps; original sportsbook publication/executable availability is not verified.

Analyze requests may process one exact matchup per bounded request; the interface discloses that scope. They retrieve available complete-game distributions, or request a10,000-game run when supported. CFB and NFL identities/models remain separate. Exact player, game, kickoff, statistic and histogram count must reconcile. Push probability is separate from strict over/under frequency. Missing distributions, unresolved identities or unavailable current evidence withhold estimates. NFL roster metadata now retains the published ESPN crosswalk ID; the actual simulation and fitting algorithms are unchanged.

Raw statistical threshold frequencies are not calibrated sportsbook win probabilities. Current calibration, full injury/roster/weather adjustments, participation/settlement rules and fees are incomplete; calibrated probabilities and after-fee EV remain unavailable. Anytime-touchdown prices with no numeric provider threshold keep a null threshold rather than inventing0.5. No new model promotion or accuracy claim was made.

## Persistence and privacy

The existing Supabase project `qdtdjbapdipopncklsdb` is reused. Migration21 only extends the existing empty public quote table's provider constraint and enforces sportsbook-family classification for PropLine. Original provider rows, private research and Auth-user counts were unchanged; RLS and immutable-history triggers remain enabled. Migration source matches native version20261031220149. Disposable PostgreSQL tests verify both sports' writes, quote immutability, family separation and existing ownership/financial invariants.

Shared quote writes still obey the existing450MBreserve. The database was451.62MB during inspection, so new public quote persistence remains paused. This release does not delete history or waive that guard. Fresh market discovery is served from the Render cache. Authenticated analysis can save a bounded first100-row private research snapshot under the owner's RLS-protected records, with a separate signed-in history/reopen interface. Saved snapshots are explicitly historical, never presented as current executable offers. Private production sign-in/save/restart tests are not claimed without an isolated authenticated account.

The existing authenticated operator schedule now refreshes PropLine NFL and CFB boards. Foreground screens refresh while visible. Actual source changes are rechecked before new model evidence is displayed. Injury-triggered numerical adjustments remain limited to supported verified inputs; no arbitrary availability probabilities or multipliers are introduced.

## Preserved/unavailable

Wallet, financial accounting, previous predictions, conversations, PWA assets, NFL engine and existing private simulation service are preserved. OpenAI generation and Apple sign-in remain separately unconfigured. The known email-confirmation return-URL setting still requires operator correction. ParlayAPI remains disabled because its official documentation returned access-denied; no guessed fallback is advertised as operational. Physical iPhone installation and continuous unattended injury-update behavior are not claimed from browser emulation or a single test run.
