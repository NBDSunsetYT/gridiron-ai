# Probability pipeline repair — 11.0.1

This changes the existing app; no account, financial record, prediction or old simulation was reset or deleted.

## Observed failure

On 2026-11-01, the actual PropLine CFB row for Nick Poulos, ESPN athlete 5228762, passing yards over 192.5, provider event 542189 / ESPN event 401866453, reproduced the reported generic message. The market had an observed price while the model side was null. The nested analysis check concealed the failure.

A direct request to the existing CFB analyze route returned HTTP 429: daily complete-game capacity reached. PostgreSQL confirmed 500,000/500,000 games consumed in the shared UTC daily budget. Background NFL research and foreground NFL/CFB requests shared this pool. Existing failed NFL jobs also named the daily limit. This is an application resource guard, not evidence that every player lacked historical observations.

Two additional defects made the experience worse:

- CFB and fallback/joint NFL output depended on short-lived Runtime Cache entries while completed compute reservations remained durable. After a cache expired, the app could know a run completed without retrieving its distribution.
- PropLine quote row IDs include prices and observation timestamps. A refreshed quote could stop matching the ID captured before research, even with the same stable player/event/market definition. Discovery-only refreshes also discarded loaded model comparisons.

No provider credential failure was observed in this reproduction. The NFL market board separately supplied no verified current rows; it is not replaced with another sport or invented prices. Render's scoped error log query returned no matching error entries. Vercel's recent probability log query returned no entries; the actual API responses and database rows provide the positive failure evidence. An initial one-hour Vercel log query exceeded the plan's retained window and was narrowed to ten minutes.

## Implemented behavior

Probability requests create a bounded server-side job, return HTTP 202 with its ID, and expose read-only progress polling. Loading, player resolution, preparation, running, calculation, ready, delayed, source failure and failed execution are distinct states. Polling does not consume the analysis-creation rate limit. The dialog supports Retry Analysis, aborts obsolete UI requests, and updates its source card when a result finishes.

The market resolver uses stable provider event/player IDs, exact market/side/threshold/book, verified ESPN event mapping, source kickoff and the model's identified matchup. Display-name differences and refreshed quote IDs cannot select a different player or threshold. Missing player IDs, event crosswalks, historical distributions and availability mixtures are reported specifically. No name-only, cross-sport or arbitrary statistical fallback is introduced.

New NFL fallback, CFB and joint runs save immutable compressed aggregate objects through the existing research storage adapter plus small sport/input-specific references in the existing shared operational index. Current input fingerprints are verified before reuse; changed inputs produce different references. Legacy saved records and Runtime Cache readers remain compatible. Public jobs contain no user identity, stake, financial record or private conversation. Only ready results are saved to authenticated private probability history.

Supabase retains all private accounts and ledger data. Existing Atlas/R2 opt-in routing remains unchanged. Neither is claimed as activated. No full-run play arrays are stored.

Raw probabilities use exact histogram counts K/N, Wilson 95% sampling intervals and sqrt(p(1-p)/N) Monte Carlo errors. Calibration remains separate and requires the existing attested sport/market/model-specific approved chronological artifact. A calibration lookup outage preserves the raw result. Model/scenario uncertainty remains explicitly incomplete rather than invented.

A read-only capability-protected capacity RPC leaves the hard 500,000-game limit unchanged. Background refresh stops admitting work above 300,000 games to reserve the remainder for on-demand work. Existing usage was not reset, refunded or increased. New uncomputed requests may remain delayed until the existing UTC reset when today's limit has already been reached.

## Actual-source recovery and verification

The engineering cloud workspace ran the unchanged NCAA engine for 10,000 complete games using the published SportsDataverse ESPN-derived current-season play corpus for Ohio at Akron. This was not a synthetic fixture or a hosted run outside its reservation guard. Its input fingerprint exactly matched the production worker's preparation response:

`eb62eec8056601596c28c6582ce2f3754c8cf2eb875747709ab78bba03363739`

The compact result contained 42 player distributions and approximately 386 KB of JSON including the bounded representative game. It was saved through the authorized recovery worker, with execution provenance, and reopened with matching identity and checksums. No hosted budget, user record or financial record was changed. The repaired application can retrieve this genuine result without recalculating it.

For Nick Poulos over 192.5 passing yards, the actual recovered histogram counted 3,292/10,000 outcomes, a raw conditional rate of 32.92%. This is a historical-participation baseline, not a calibrated probability, an injury-complete forecast, a live price or a wagering recommendation. Other verified thresholds are recorded in the actual-source report. No forecast superiority is claimed by a pipeline repair.

The new capacity function migration is additive and read-only. Rollback can remove that function only after reverting its caller. Keep the new probability object/reference readers for results saved after this repair; never purge those objects or reset accounting data to roll back code.

See the production verification report for exact passing tests, deployment identity, current provider limitations and mobile scope. A simulated viewport is not a physical iPhone installation test.

A further actual-source joint run exposed a storage classification defect: a
statistical contract's `settlement` definition was mistaken for a private
financial settlement. The guard now accepts only a tightly validated statistical
definition attached to an identified probability row. Financial amounts, account
records and other settlement payloads remain rejected. An actual two-leg CFB
run yielded 2,342 joint successes from 10,000 shared games; it was recovered with
the same verified source fingerprint and explicit engineering-worker provenance.

A source outage after the first trace also expired current PropLine prices.
Verified boards now retain compact private object references for at most 24-hour
definition recovery. An unavailable live feed can expose those previously
verified definitions for independent threshold research. Their original quote
timestamps remain unchanged, prices are marked historical, and current
break-even/value fields remain unavailable. No never-observed NFL market is
created as a fallback. This does not claim a still-listed executable contract.

## Production delivery

The unchanged app URL is https://gridiron-ai-gray.vercel.app. Deployment
`dpl_CibbDbaP3J7mLwSCxfo7F1CM6x8d` is READY with runtime source commit
`917f4b5356846c949b2e4b4dea415fb200e25a73`. No Render service was replaced,
credentials were not moved, and no paid resource was provisioned.

Passed: 690 TypeScript tests, 19 relevant Python tests, nine existing PostgreSQL
suites plus the new capacity suite, 66 desktop/mobile regressions and 14 final
focused browser regressions. On this actual deployment, 13 end-to-end source/API/
recovery/mobile checks and 15 PWA/privacy/offline checks passed.

The real iPhone-sized Chromium UI displayed 3,292 / 10,000 for the verified
Nick Poulos passing-yard threshold. The four CFB player categories, independent
game-winner and hypothetical-total thresholds, same-game joint probability,
subsequent result retrieval and guest denial of private records were exercised.
The live provider had no verified fresh NFL rows at test time; seven checks of
actual historical NFL outcome distributions were recorded separately and are not
labeled current market or accuracy evidence. Current CFB prices were delayed, so
the deployed tests exercised explicitly historical verified definitions and
independent model research without a current break-even value.

Physical iPhone installation, an authenticated private cross-device session and
prospective calibration were not established by these checks. New uncomputed
hosted runs can remain delayed until the unchanged daily limit resets at
2026-11-02 00:00 UTC. Existing matching persistent results remain available.

Reports: [full verification](reports/probability-repair-verification.json),
[production workflow](reports/probability-repair-production.json),
[PWA](reports/probability-repair-pwa.json), and
[NFL historical arithmetic](reports/probability-repair-nfl-historical.json).
