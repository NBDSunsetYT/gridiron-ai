# V25 frozen evaluation harness — Gate 2

The original V24 numerical law is retained. The harness reconstructed **320 model/window traces across 52 of 53 categories** using their existing primary chronological protocols, original fitted artifacts, forecast identities, seeds and marginal draw counts. Point estimates and 90% intervals matched the frozen forecasts at 1e-12 tolerance; MAE, RMSE, bias, CRPS, calibration diagnostics and 50/80/90/95% coverage matched the stored metrics at 1e-10 tolerance. No models were fit or reselected.

CFB targets remains unsupported in both windows because the original verified source has no target observations. No replacement dataset or zero target labels were invented. The [machine-readable reconstruction](V25_EVALUATION.json) contains every trace's numerical results and sample sizes. The original per-category leaderboard and conditional selection decisions remain unchanged.

This is a deterministic reconstruction of exposed conditional research, with **zero new independent games, zero strict pregame games, zero joint-probability accuracy observations and zero production promotions**. Diagnostic CDF thresholds remain distinct from actual market lines. Missing historical lines produce marketless evaluation; they do not acquire synthetic prices.

The existing protected final-test and locked confirmation sets remain sealed. No new untouched cohort was declared. The harness includes tests rejecting simultaneous/future training, outcome labels in features, overlapping cohorts, protected development games, and unknown/exposed final-period status. A synthetic analytic golden file checks scoring, and deterministic game-cluster bootstrap tests preserve the original method.

Revision r2 additionally binds all original cohort/report/registry editions by SHA-256 and rejects unknown final-test exposure. The first replay is retained as a superseded checkpoint; no statistical predictions or scoring law changed.

Measured r2 replay: 56.951 CPU seconds, 57.227 wall seconds, peak RSS 967440 KiB. Eight focused reconstruction/golden/isolation tests passed. All work ran locally.

```bash
# Requires the preserved private V24/V25 artifacts and immutable r2 protocol.
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python scripts/replay-accuracy-v25.py
python -m unittest modeling.test_accuracy_v25_evaluation modeling.test_accuracy_v25_recon
```

Only an absent protocol may be registered with `--register`; never overwrite an existing protocol. New input editions require a new revision. This harness stage is not a new champion-selection or predictive-accuracy result.
