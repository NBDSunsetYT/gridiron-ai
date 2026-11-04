# Accuracy release 12.3 (development checkpoint)

- Corrected the Over-trained Platt transform for Under selections, including complementary intervals and training-domain checks. Half-integer Over/Under estimates now remain complementary; integer thresholds retain equality mass.
- Added a fixed Jeffreys beta-binomial historical fallback, `(hits + .5) / (games + 1)`, with separate raw observations and a conditional posterior interval. It never invents complete simulated games or calls itself calibrated.
- Publication requires two separate chronological annual audits, game-cluster bootstrap and circular two-week block sensitivity checks, Bonferroni adjustment over 52 predeclared NFL stat/role groups, improved Brier and non-worse log loss. Eleven of 33 observed NFL groups passed both 2025 and 2026 monitoring gates. Every failed group remains in the audit artifacts. No college artifact is inferred from NFL validation.
- Audits use actual versioned public nflverse player statistics. Thresholds are derived only from earlier-season observations. They are retrospective statistical thresholds, not invented historical sportsbook prices. First-publication histories are unavailable; this is not prospective contract calibration or proof of market advantage.
- Auditing runs offline, and frozen release artifacts are loaded by the worker. No per-visitor retraining or simulation-count reduction was added. Artifact availability is checked against the prediction timestamp.
- Restricted hierarchical player samples to game IDs already admitted to that player's source evidence, preventing excluded team-history rows from reentering a selected model.
- Existing public historical hit rates now use a distinct heading. The probability detail service preserves supported calibration and new posterior evidence instead of dropping it.

Sources and complete results: `modeling/validated/history-validation-nfl-2025.json`, `modeling/validated/history-validation-nfl-2026.json`, and `docs/reports/history-regularization-audit.json`. Reproduce with `python scripts/audit-history-regularization.py --test-season YEAR --out PATH`.

This accuracy checkpoint shipped with version 14.0.0 after staged and live checks. See GAFIE_GALL_14.md and the production verification reports for the full release scope and remaining limitations.

Storage investigation: Render's free gateway was not suspended, showed about 202 MB of 512 MB memory and low CPU, with no errors during 04:00–06:00 UTC on November 4. Vercel remained reachable and its remote cache was enabled; billing charges API returned `costs_not_found`, so account-wide quota consumption was not established. Supabase measured 475,264,691 database bytes. A non-destructive `VACUUM FULL` on the old shared prediction table reclaimed about 1 MB; all 28,660 prediction IDs and their checksum remained identical. This did not resolve the underlying live-data storage pressure. No records were deleted and no paid resources were added.
