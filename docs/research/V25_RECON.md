# V25 implementation reconnaissance

Branch: `research/accuracy-v25`, from V24 local commit `bfa1c30cc24ff57aefb2045eb3472cdb699b5c6a` (tree `508e039e57cba2a9c40af20c0aa556042bfa0432`, identical to published V24 commit `17db382160d47953ae0b35c7256124c1d6082c55`). This is an audit and baseline-reproduction stage. Production, staging and the separate market-V18 research branch are not merged.

The inspected primary records are `FULLGAME_V23_REPORT.md`, `dynamic-v24-report.md`, `specialized-v24-report.md`, the 53-row CSV/Markdown leaderboard, 255 versioned registry entries, the 100-head bank, eight tournament protocols, original replay receipts and protected-cohort definitions. Source inspection covers `dynamic_v24/completion/{models,selection,data,efficient_data,bank,joint,basketball_engine}.py`, the V23 ledgers/rules, V24 dynamic kernels/live store and existing probability/provider boundaries.

## Existing implementation and missing scope

| Requested component | Classification | Actual implementation / limitation |
|---|---|---|
| Per-statistic tournament | Existing | 53 league/category slots; 2,609 candidate/window evaluations across eight protocols. These are not 2,609 different architectures or complete-game forecasts. |
| Rolling and EWMA baselines | Existing | Earlier-game means and exponentially weighted histories; retained as references. |
| Regularized regression | Existing | Opponent Ridge, Lasso and Elastic Net. Fixed inner selection, not a final-period parameter search. |
| Hierarchical / empirical Bayes | Existing, limited | Regularized player/team identity effects and empirical shrinkage; not a full Bayesian posterior. |
| Boosting and quantiles | Existing | Histogram boosting and median quantile regression. Median heads cannot become expected-value heads. |
| Count/hurdle/mixture models | Existing, limited | The named negative-binomial family fits a Poisson log-link point mean, then estimates NB predictive overdispersion; it is not NB maximum-likelihood regression. Hurdles and residual mixtures exist. |
| Opportunity × efficiency | Existing, incomplete accuracy | Separate team exposure/share and conditional efficiency. NFL/CFB passing alternatives failed later-window generalization. |
| Specialized model registry | Existing | Expected-value, median and distribution slots differ. Candidate availability is delayed until confirmation ends. No production approvals. |
| Marginal conditional winners | Existing | CFB receiving TD expected value: residual mixture; NBA rebound expected value: Lasso; NBA steal expected value: hierarchical effects. No approved probability replacement follows from those wins. |
| Football complete-game kernel | Existing, incomplete forecasting | V23 accounting/rules and V24 shared-event adapter. Unsupported anonymous opportunities remain team credits. CFB clock/administrative pace certificate incomplete. |
| NBA complete-game kernel | Existing, incomplete forecasting | Shared shots, eligible rebounds/assists and constrained minute budgets. Missing/returning participant evidence blocks some adapters. |
| Selected heads inside simulator | Incomplete | Mechanics adapters inject exposure/actor/yard/minute/shot heads. Head-to-simulation distribution compatibility and independent joint accuracy remain unproved. |
| Pregame evidence | Missing for strict qualification | Publication-complete historical injuries, lineups, expected participation and original statistical editions are unavailable. Unknown availability is not healthy. |
| Calibration / distribution scoring | Existing diagnostics, incomplete approval | CRPS, CDF Brier/log loss/ECE and 50/80/90/95% coverage. Training-quantile thresholds are not actual historical prop lines; no approved new calibrator. |
| Momentum/fatigue | Existing component research, incomplete full game | A/B/C next-event comparisons. Football momentum did not consistently improve; NBA action context improved but shooting-success effects did not. No physiological measurement or arbitrary hot-hand bonus. |
| Live continuation | Existing mechanics, incomplete live accuracy | Ordered/revised events, cached snapshots, freeze states, bounded outbox and remaining-game-only continuation; no qualified live calibration/latency cohort. |
| Production reference comparison | Incomplete | Matched NFL production-source QB replay for a subset; immutable deployed forecasts missing for most categories. V23 final-conditioned mechanics cannot be called a pregame reference. |
| Historical market blending and CLV | Missing verified sample | Existing PropLines / DraftKings Predictions adapters stay separate. No timestamped historical settlement-complete market sample was graded in V24. Never invent a line. |
| Rebuild tournament or engine | Unnecessary | Reuse existing model families, bank, ledgers and gates. Add missing compatibility/evidence checks only after baseline replay. |

## Scope of the saved numerical baseline

V24 registered 676 distinct matchups: NFL 311, CFB 191, NBA 174. Statistic-specific counts overlap and must not be summed. The final source-quality pass rejected 17 NBA games; on-court rebound opportunities remain a historical miss/minute proxy. Original V24 has zero strict pregame full-game forecasts, zero joint accuracy comparisons, zero verified historical lines graded and zero production promotions.

The 342 older examined games and all V19–V24 development/confirmation outcomes are exposed research, never a new untouched final period. The 79 sealed final-test games and locked confirmation cohorts stay protected.

Gate 1 requires actual frozen-model replay on reconstructed identical feature inputs, original seeds, and model/source checksums. It does not require a new fit or new simulations. A missing private source/artifact blocks dependent numerical work. See `V25_DRIFT_AUDIT.md` and the generated replay receipt for actual execution status.
