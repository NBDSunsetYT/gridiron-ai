# V28 research checkpoint

Branch: `research/forecast-certification-v28`, from V27
`4ed0136844df1537e44973296da6d8dbe9e61c22`. Research only. Production,
financial records, model registry, protected cohorts and prior forecasts are unchanged.

The NBA bank stopped at June 2026 despite owned 2026–27 data. An explicit
opt-in reader admits the missing season, excludes protected IDs before row
materialization, verifies player/team accounting and hashes source editions.
It does not change old experiments' default input loaders. Current release:
122 admitted games, one rejected inconsistent box. Corrected boxes retrieved
after historical games are not verified historical pregame editions.

An empirical-Bayes minutes prior now covers all modeled roster IDs, including
previous-team history and sparse-player population priors. Conditional
availability scenarios, sourced restrictions, exact 240-minute regulation and
25-minute overtime budgets, multiple-chain diagnostics and five-player tapes
are implemented. A rotation draw is not a completed basketball simulation.

## Executed conditional validation

| Experiment | Games | Graded player rows | Recent rolling MAE | Candidate MAE | Game-paired candidate-minus-reference MAE, 95% bootstrap CI |
|---|---:|---:|---:|---:|---|
| Gaussian constrained rotation, development | 15 | 389 | 4.9165 | 5.9132 | +1.0310 [0.6740, 1.3960] |
| Historical zero-minute hurdle, later confirmation | 6 | 155 | 4.8535 | 4.9661 | +0.0814 [-0.3119, 0.5138] |

Neither candidate beat the recent-history reference. No promotion. The later
comparison uses source-adjusted rolling zeros for documented out players;
the first comparison used the original unadjusted reference. They are separate
cohorts, not a before/after paired estimate. All candidate team scenarios
converged and conserved minutes, but historical roster and availability
completeness still fail full-game eligibility. Unknown is never healthy.
The first experiment withheld one team when its inferred active-list scenario
contradicted more than 15 available/conditionally active players. The second
experiment respects sourced available participants first and bounds the rest.

On the first experiment's 343 common player rows, stale June-history rolling
MAE was 8.3481 minutes versus 4.8965 after refreshing history. This diagnoses
staleness on a conditional cohort; it is not production-champion superiority.

Three dated official NBA injury PDFs were recovered (November 4, 5 and 6,
2026 at 5 p.m. Eastern). The first two have 199 parsed facts/rows. Matching
requires exact team, player and event date; missing rows stay unknown.

Reproducibility: `V28_ROTATION_R{1,2}_RESULTS.json.gz` contains aggregate
metrics/protocols; matching `CODE` files preserve exact source editions.
Private immutable feature snapshots and grading receipts remain in
`artifacts/forecast-certification-v28/nba-rotation-r{1,2}`. Raw datasets and
licensed/private source bodies are not published. Previously exposed games
are excluded from these cohorts; neither cohort is a sealed final test.

Commands:

```sh
python -m unittest modeling.test_rotation_v28 modeling.test_recent_nba_v28
python scripts/v28-sources.py
python scripts/v28-nba-rotation.py
python scripts/v28-nba-rotation.py --confirmation
```

Twelve component tests passed. Historical source receipts must be restored
before rerunning immutable experiments. Existing result paths refuse divergent
rewrites. NFL/CFB timing work and the final checkpoint are still in progress.
