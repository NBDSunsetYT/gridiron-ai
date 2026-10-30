# Empirical research baseline

This is a working, auditable baseline, not an opponent-adjusted NFL forecasting model. It does not invent player usage or retrieve game logs. Supply legally obtained comparable real observations, oldest first, with timezone-aware `observed_at,value` columns. Keep one player/statistic/role population per dataset. Never mix statistics or use outcomes not available before your cutoff.

```sh
python modeling/pipeline.py observations.csv --threshold 64.5 --direction over --odds -110 --source 'Provider citation and extraction date' --out model-report.json
cd modeling && python -m unittest
```

The estimator uses an empirical distribution and a Jeffreys-smoothed binomial hit probability, with pushes accounted for separately. TypeScript produces Wilson 95% intervals and a histogram. At least 20 non-push observations are required. Each rolling prediction fits its strict historical prefix; performance is hidden until at least 20 held-out outcomes exist. CSV rows must have unique, increasing timestamps. Python reports dataset SHA-256 provenance.

Freeze market threshold, feature choices and model specification before evaluating a holdout. Choosing a line after examining all outcomes creates selection bias that rolling splitting cannot repair. Recorded performance describes only the submitted observations; it is not the application's verified forecasting record. Historical NFL predictions, calibrated trained models, opponent adjustments, hierarchical player models and injury-aware ensembles are not provided without historical datasets and validation work.

Parlay research can use aligned boolean scenario rows to preserve observed dependence. Individual-leg estimates alone do not identify joint probability. Independence scenarios require explicit opt-in and remain visibly hypothetical. Wilson intervals cover sampling uncertainty, not model misspecification, data errors, market pricing rules or future regime changes.

Financial calculations use Decimal cents elsewhere. Model probabilities use IEEE-754 floating point, appropriate for statistics, and never post ledger balances.
