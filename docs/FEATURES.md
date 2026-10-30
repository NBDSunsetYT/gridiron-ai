# GRIDIRON AI 4.0 capabilities and limits

Use [DELIVERY_V4.md](DELIVERY_V4.md) for executed checks and [AUDIT_V4.md](AUDIT_V4.md) for evidence boundaries. The 2.0 matrix is preserved as [FEATURES_V2.md](FEATURES_V2.md). Missing coverage remains visible; QA fixtures are never presented as real production markets, injuries or P/L.

| Feature | Working scope | Remaining boundary |
| --- | --- | --- |
| Auth advisor | No SQL/RLS finding in final remote advisor | One warning: leaked-password protection disabled; optional dashboard setting/plan needed |
| Cloud identity/persistence | Configured live Supabase Auth/PostgreSQL with five applied migrations, HttpOnly sessions, owner RLS on all 47 public tables, authenticated financial RPCs, refresh/restart continuity | Public HTTPS frontend deployment still required; live backend is not a hosted app URL |
| Legacy continuity | Explicit SQLite workspace, owner guards, consistent snapshots and checksummed additive migrations | Not PostgreSQL RLS; single persistent Node/volume deployment; no silent cloud fallback |
| Money/ledger | Decimal/exact cents, balanced atomic postings, deposits/withdrawals, wagers, returned stakes, transfers, settlements, cash-outs, refunds, audit/reconciliation and reports | Personal records, no sportsbook account synchronization or wager execution |
| Cloud account controls | Confirmed owner deletion Edge Function and session revocation, scoped exports/preferences/conversations | Provider/host retention and off-site backups remain operational responsibilities |
| Encrypted backup | All 43 typed owned table families included; actual 149 plays/285 games and raw financial reconciliation checked; auth secrets excluded | Financial/app history import and saved-research/watchlist namespaces work; full normalized typed reconstruction incomplete, raw archive preserved; project restore still needed for complete typed recovery |
| NFL warehouse | Actual public schedules and normalized play import with provenance, hashes, null missing availability, owner RLS, immutable snapshots and duplicate-safe retry | Verified coverage is 285 games and 149 retained single-game plays in the QA owner; not comprehensive league/player-usage coverage |
| Binary contracts | Manual verified YES/NO rules, exact fee/price arithmetic, immutable quotes/forecasts/settlements, generated rule matching and separate paper portfolio | No authorized direct DK Predictions feed or executable fill/settlement verification |
| Sportsbook prices | Manual/CSV markets and licensed-feed adapter with explicit provenance | Provider credentials/entitlements required; Hard Rock/DraftKings coverage never assumed |
| OCR | Screenshot extraction/review tooling where exposed | User must verify every extracted price/selection; not a connected licensed feed |
| Simulation/parlay | Signed fitted historical artifacts, seeded complete-game runs, same-run joint outcomes, explicit independence comparison and verified combined-quote EV | Evidence/cohort/model limitations remain; historical or synthetic test inputs are not current live predictions; actual historical 50k/100k mechanics/throughput checked; actual connected cloud 10k+1k bootstrap/persistence passed on retrospective data; parameter interval absent in the separate speed run |
| Research models | Bayesian, regularized, boosted candidates and calibrated ensemble; 816 chronological home-win holdouts with real report | Ensemble Brier 0.224483 trails indicative market 0.210157; `productionEligible:false`; no player-prop/simulator validation implied |
| Injuries | Sourced manual records, freshness, confirmed-out distinction, referenced invalidation and supported evidence-backed reruns | No connected official live wire; unsupported cohorts/interactions block; no guessed availability multiplier |
| Research pipeline | Owned scheduled preferences/runs, visible-page updates and operator-worker path | External closed-app scheduler and paid sources require operator setup |
| AI research | Server-side OpenAI streaming/tool integration and persistent owner conversations with complete history pagination | Key/live response test absent; no pretend web search or unavailable-source claims |
| PWA/offline | Responsive mobile interface, install assets, safe offline shell, optional encrypted read-only historical snapshot | Physical Safari install unverified; device snapshot manually refreshed, no offline transaction sync |
| Native iPhone | Real Capacitor/Swift project, source/preparation/cap-sync checks, Keychain/session/navigation code and private signing scripts | No Swift compile/IPA/device install on Linux; Mac/Xcode/Apple signing and hosted HTTPS backend required; no App Store/TestFlight |
| Notifications | Persistent in-app notices and authenticated encrypted native token-registration path | APNs credentials/sender/delivery not connected; registration is not delivery |
| Production deployment | Source, Docker/service and migration/recovery guides supplied | Frontend hosting/TLS not deployed; no claimed public URL or commercial release certification |

The app does not place wagers, bypass geolocation, invent missing evidence or guarantee outcomes. Source downloaded to iPhone Files does not run the server.
