# GRIDIRON AI10.0 — verified upgrade scope

This extends the existing app; it does not replace its deployments, ledger, models or database. Source checkpoint: `checkpoint/pre-v10-df565dc`. Before schema changes, an AES-256-GCM encrypted private-data checkpoint was written outside the repository and successfully decrypted for verification. Existing accounts and records were preserved. The new additive migration is `20261031225446_v10_saved_workspaces.sql`.

## Operational changes

- Primary navigation: Home, Live, Props, Combos, Wallet. Games, simulations, AI Research, history and saved research remain accessible above the content; original deep links and advanced tools remain available.
- Public NFL/CFB scoreboard reads actual published ESPN events. A provider in-progress state plus a recent successful observation is required for LIVE. Known stale publication times suppress LIVE. Provider publication and observation times are distinct. Failures retain explicitly stale observations, without estimating scores. Server requests are deduplicated and cached30seconds; visible screens refresh30seconds. This is polling, not a guaranteed real-time feed. The college board covers the published FBS group; comprehensive FCS coverage is not claimed.
- Compact PropLine cards show selection, reference odds, raw statistical estimate, availability and source observation. Research limitations and sampling intervals are expandable. Selections can be sent directly to the combination builder. NFL and CFB and their identities remain separate. Sportsbook prices remain separate from DraftKings Predictions contracts.
- Research drafts, available above the content, use the same versioned editor and cloud-save protections in a separate workspace kind. Research notes and combination recovery copies are separated by owner, sport and kind.
- Editable combinations have debounced cloud autosave, confirmed save states, exact idempotent retries, conflict rejection, immutable version rows, restoration into a new revision, source quote retention, notes, JSON/CSV export and validated import as a new combination. User-entered threshold/selection edits are hypothetical. Current-price refresh matches exact original definitions against a bounded first page, with unavailable prices explicitly omitted.
- Device recovery copies are encrypted in IndexedDB using non-exportable AES-GCM keys, scoped to the signed-in account and sport. Guest drafts survive refresh in sessionStorage and can be recovered after app sign-in. Neither is the authoritative database, and no financial records or session credentials are stored in these drafts. Recovery creates a new cloud combination rather than overwriting a newer device's edits. Reopening the offline app shell itself still requires reconnecting to access the authenticated editor; this is interrupted-edit recovery, not a fully offline account app.
- Hypothetical payout uses Decimal arithmetic and explicit rounding down to cents before profit reconciliation.20USD at3.50x returns70USD gross and50USD profit before costs. The entered fee is charged on a winning return only; other fee schedules require separate verified pricing. A multiplier is a user assumption, not an executable offer. The new editor withholds joint probability without aligned simulation outcomes; the existing correlation-aware simulation lab is preserved.
- Account backups now include both workspace tables and every version through owner-scoped pagination. The existing legacy backup importer archives normalized typed data; it does not automatically reconstruct those typed tables. Combination JSON import restores an editor copy. Project-level restoration is the complete recovery path.
- The private AI toolset can query owned saved combinations and their source snapshots. General AI responses still require the existing separately configured AI provider. No language-model probability calculation was added.
- Authenticated CFB prop analysis also attempts to save its complete verified simulation through the existing durable private-history path. A failed private simulation save is separately reported; no replacement result is invented.

## Data protection and recovery

New tables `research_workspaces` and `research_workspace_versions` have RLS. Authenticated clients can only SELECT their own rows; direct table INSERT/UPDATE/DELETE is denied. An authenticated invoker RPC calls a private function that checks ownership, serializes edits per workspace, validates the expected revision and appends an immutable version in the same transaction. All timestamps come from PostgreSQL. Replayed mutation IDs must have identical content. Foreign ownership is rejected. No service-role key is needed in the browser.

Use Settings' encrypted account export and the builder's JSON export for personal recovery. Preserve the private recovery key and ciphertext outside source/deployments; the key is deliberately excluded from releases. On project recovery, restore the existing project backup to a separate recovery environment first, verify RLS and financial reconciliation, then coordinate production restoration. Do not drop the new tables after users have saved drafts. Application rollback can restore the preceding Vercel deployment while leaving the additive tables and all versions intact.

## Audit and outstanding requirements

| Area | State and evidence |
|---|---|
| Exact ledger, deposits/withdrawals, settlements and account isolation | Existing implementation preserved; PostgreSQL and browser regression suites exercise accounting. No live personal wagers were entered. |
| Distinct Predictions/Sportsbook/custom wallet accounts | Still incomplete: legacy DraftKings/Hard Rock account labels are preserved. Recorded wager instrument distinguishes event contracts from sportsbook bets, but separate custom account management was not added. |
| Versioned combination cloud writes | New migration applied; real PostgreSQL RPC write/retry/conflict checks passed inside a rolled-back transaction. Synthetic two-owner PostgreSQL integration tests passed. |
| Full sign-in, cross-device cloud saves | Not production end-to-end verified without an isolated authenticated QA identity. Existing email-confirmation return-URL configuration remains unresolved through available integrations. |
| NFL/CFB complete-game simulation engine | Existing engine preserved. This release does not claim newly calibrated injury/roster/weather models or a new promoted statistical model. |
| PropLine NFL/CFB references and injury reports | Existing authenticated Render adapter preserved. Availability and current inventory depend on the provider; quote freshness is enforced. |
| DraftKings Predictions contracts | Authorized exact-contract feed remains unconfigured. Sportsbook prices are never substituted. |
| Shared automatic quote/prediction warehouse persistence | Existing storage protection remains active above the450MB public-research reserve. No historical data was deleted to regain space. User drafts remain separate private writes. |
| Whole-slate automatic simulations and research | Incomplete: current prop analysis processes one bounded verified matchup per request, with unavailable evidence withheld. |
| Model calibration, full injury scenarios, automated numerical injury resimulation | Existing support remains partial; unavailable validated probabilities are not invented. |
| Heavy compute hosting | Existing private Python service preserved; Render remains the PropLine gateway. No new paid worker was provisioned or unauthorized infrastructure migration performed. |
| Push notifications, Apple sign-in, general AI generation | Existing external configuration limitations remain; this release does not claim these are connected. |
| iPhone | Responsive/browser/PWA tests are scoped checks; physical installation is not claimed. |

The supplied10.0 text ends at the financial test list. No missing continuation was assumed. This document is an implementation scope report, not a claim that every master requirement is complete.
