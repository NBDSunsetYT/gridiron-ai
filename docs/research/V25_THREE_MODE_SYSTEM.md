# V25 objective modes and automatic routing

This extends `research/accuracy-v25`; it does not restart V18, modify the V24 registry, or deploy research models. The existing 53-category catalogue, 255 immutable registry records, tournaments, adapters, protected cohorts, and original forecasts are retained.

Accuracy objectives and historical evidence modes are separate axes:

| Accuracy objective | Primary use | Existing registry slot |
|---|---|---|
| A — probability | Binary and threshold probabilities; distribution quality | `distribution` |
| B — numerical | Conditional means; explicitly requested medians | `expected_value`; `median` |
| C — market research | Verified market residuals, CLV, settlement-aware returns | No independently validated existing market-relative head; withheld |

V23's `historical_mechanics`, `conditional_diagnostic`, and `strict_pregame_forecast` names are unchanged. A mechanically correct replay cannot become an accuracy claim by choosing objective A, B, or C.

## Implemented routing layer

`modeling/router.py` reads and checksum-verifies the existing registry. No new registry or family winner is created. Requests have stable league/event/team/player identities, explicit output objective, and versioned exact threshold/equality rules when relevant. Means cannot use median heads; arbitrary quantiles are withheld without a validated requested-quantile head.

A strict research route requires the original registry decision to pass, verified pregame evidence, reproducible production-reference comparison, two independent chronological validation windows, fit/calibration/selection before the request, unprotected game manifests, source-version hashes, validated freshness limits, and the existing mechanics and joint-probability gates. A compatibility certificate must bind the selected head, exact artifact, immutable inputs, and shared-game model. Conditional winners remain visible research candidates, not approved routes.

Eligible alternatives must share validation cohorts. A lower aggregate error alone cannot resolve uncertain head-to-head selection. Numerical expected-value routing uses the existing RMSE objective, medians use MAE, and distributions use CRPS (Brier for binary categories), with probability-specific validation additionally required. Exact-threshold validation cannot be replaced by training-quantile CDF diagnostics. No fixed model/market weight or correlation threshold is introduced.

`predict` only retrieves a checksum-verified cached output bound to the request, head, input snapshot and joint model. It does not fit, simulate, schedule, or mutate production state. Unknown availability, stale inputs, future fits, incomplete qualification and protected events withhold the route.

Fourteen initial software tests passed, including analytic numerical/probability scores, push settlement, read-only real-registry routing, source identity and freshness, cutoff failures, protected events, and cache bindings. The positive authorization-path fixture explicitly mocks existing joint gates: it demonstrates routing software, **not** a real historical forecasting certificate.

## Full-plan integration map

The original uploaded plan had 13 sections; the revised request names 15 logical stages. All are retained below. Completing a software interface does not pass its scientific gate.

| Logical stage | Existing implementation / integration point | Current scientific status |
|---|---|---|
| 1. Drift audit and reproducible baseline | `V25_RECON`, `V25_DRIFT_AUDIT`, original 34-trace replay | Passed for documented six-category replay; original-fit hash drift disclosed |
| 2. Frozen historical evaluation | `accuracy_v25/evaluation.py`, 320 original model/window traces | Software/reproduction passed; no new independent cohort |
| 3. Golden-file regression | `test_accuracy_v25_evaluation.py`, analytic fixture, seeded replay | Passed; no scoring-law changes to original artifacts |
| 4. Leakage probes and negative controls | `accuracy_v25/leakage.py`, twelve actual fixed-model controls | Passed documented software/diagnostics; no fabricated market shuffle |
| 5. Availability and freshness | Existing source-lineage guard plus objective router | Strict historical evidence remains insufficient; dependent new fitting pauses |
| 6. Opportunity/efficiency models | Existing V24 53-category tournament and registry | Retain conditional wins and rejected passing challengers; no new fit authorized by missing evidence |
| 7. Joint-event improvements | Existing V23/V24 ledgers, `completion/joint.py`, bank and certificate gates | Mechanics adapters retained; strict model-bound compatibility incomplete |
| 8. Variance and interval calibration | Existing frozen draw law; numerical coverage, quantile and Winkler scoring | No new interval/calibration model accepted |
| 9. Regimes/weather/rest/travel/kickers | Existing engine inputs and historical source gates | No new verified point-in-time covariates claimed; unsupported inputs remain missing |
| 10. Market information/settlement | Existing PropLines and DraftKings Predictions adapters remain separate | No verified historical closing-price cohort; marketless evaluation required |
| 11. Mode A evaluation | Proper Bernoulli/distribution scores and separate probability route | No new probability champion or approved calibrator |
| 12. Mode B evaluation | MAE/RMSE/bias, quantile loss, Winkler/coverage; numerical route | Existing exposed conditional results only |
| 13. Mode C evaluation | Research-only objective; explicit missing-market state | CLV/returns/blending null without authentic prices and settlement evidence |
| 14. Routing/mode comparison | Read-only registry view; cached objective outputs; shared snapshots | New software implemented; strict routes stay withheld without certificates |
| 15. One-time final test | Existing sealed 79-game and locked-cohort protocols | Not opened or retuned; requires separately frozen qualified candidates |

The failed availability/qualification gate blocks new dependent training, strict joint forecasting and protected final evaluation. Independent software tests and fixed-model shadow diagnostics may continue without claiming that this scientific gate passed. No production promotion is automatic.

## Reproduction

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python -m unittest modeling.test_objective_router_v25
```

Existing artifacts remain readable without migration. New objective envelopes use version `accuracy-objectives-25.2` and router version `objective-router-25.2`; legacy V24 artifacts are not rewritten.

## Executed same-event objective shadow verification

The bounded `objectives-r1` verification regenerated the same 320 original fitted-model traces across 52 categories and checked their original point estimates, intervals and metrics. It calculated A/B/C views using one draw tape per trace. All 320 event-set and snapshot-hash checks passed. Mode-specific prediction hashes remain distinct. These tapes are original **marginal** research distributions, not a new certified joint-game simulation. The coherent-game gate is unchanged.

Existing unique games represented in these replay traces were NFL **301**, CFB **115**, NBA **94**. They are previously exposed conditional diagnostics; newly independent games and strictly qualified new pregame games are both **0**. CFB targets has no verified observations and remains unsupported. No model was fit or selected, no full-game simulation ran, no protected final outcomes were opened, and no model was promoted.

Mode A reports raw Bernoulli or training-quantile CDF diagnostics and proper distribution scores. Diagnostic thresholds are never labeled historical market lines. Mode B adds quantile loss and 50/80/90/95% Winkler/coverage scores to MAE/RMSE/bias. Mode C carries the same event set with **zero verified market observations**, so CLV, return distributions and blend weights are null.

The optional market research math has tested multiplicative and Shin devigging, strict identity/threshold/settlement/time checks, grading-only closing observations, and a bounded development-only logit-weight candidate. It imposes no fixed weight or correlation threshold. No real blend was fit. Event contracts are explicitly refused by the sportsbook devig adapter; existing DraftKings Predictions payout/fee integration is preserved separately.

The [53-category routing table](V25_ROUTING_LEADERBOARD.md) and its compressed machine-readable data preserve original candidates, references, uncertainty and rejected alternatives. Every strict route remains withheld; existing conditional winners are not relabeled as approved champions. A reporting defect for unsupported CFB targets was fixed and regression-tested without supplying fabricated metrics.

Twenty-eight focused tests passed against the exact checkpoint source, including the full 53-category catalogue and unsupported-category handling. Measured replay: **64.593 CPU seconds**, **65.360 wall seconds**, **966988 KiB** peak RSS. [Execution receipt](V25_THREE_MODE_SHADOW.json).

```bash
# At the pinned objective-shadow checkpoint, with preserved private artifacts:
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python scripts/shadow-objectives-v25.py
python scripts/report-objectives-v25.py
```

The immutable protocol records exact source editions. Later routing-only hardening must not be used to rewrite this checkpoint; reproduce it from its recorded commit. The pre-existing campaign ledger and accuracy pause remain intact.
