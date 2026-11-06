# V25 temporal guards and negative controls — Gate 3

The new research ingress rejects contemporary outcomes, final participation/rosters, post-cutoff injury reports, same-day future games, post-cutoff market captures and revised source editions that were unavailable at the prediction time. Later retrieval requires verification of the archived original edition. Uncertain/projected participation cannot authorize an unconditional forecast; separately validated scenarios are still required. These guards do not manufacture missing historical evidence or change production routes.

Eighteen focused safeguard/golden/temporal tests passed. Four actual fixed-model cases produced 12 controls, including four future-history shifts rejected before prediction. There were no new fits or model selections. This is a sensitivity audit of exposed conditional diagnostic windows, not a new independent forecasting evaluation.

| League/statistic | Fixed family | Control | Games / player observations | Original MAE | Control MAE | Paired game MAE delta 95% interval |
|---|---|---|---:|---:|---:|---|
| NFL passingYards | opportunity_pooling | team_score_context | 40 / 96 | 52.374479 | 52.708971 | [-1.5751298237415836, 1.55709947298255] |
| NFL passingYards | opportunity_pooling | player_identity | 40 / 96 | 52.374479 | 50.965432 | [-6.1921667583063895, 3.3500376397951803] |
| CFB passingYards | v20_hurdle_refit | team_score_context | 50 / 103 | 51.704494 | 52.889375 | [-1.687894753536242, 6.375733501092286] |
| CFB passingYards | v20_hurdle_refit | player_identity | 50 / 103 | 51.704494 | 51.704494 | [0.0, 0.0] |
| NBA rebounds | lasso | team_score_context | 34 / 654 | 1.984757 | 1.984757 | [0.0, 0.0] |
| NBA rebounds | lasso | player_identity | 34 / 654 | 1.984757 | 1.984757 | [0.0, 0.0] |
| NBA steals | hierarchical | team_score_context | 34 / 654 | 0.744046 | 0.746114 | [-0.0005249998855386374, 0.0042984002589460816] |
| NBA steals | hierarchical | player_identity | 34 / 654 | 0.744046 | 0.752902 | [0.0019274772054457628, 0.015692150017829982] |

The shuffle intervals are exploratory, not multiplicity-adjusted promotion evidence. A fixed-model ablation need not degrade every metric, and a lucky improvement does not become a challenger.

- NBA rebound Lasso predictions are unchanged by player-ID shuffling because this family has no identity encoder. Its coefficients for the two shuffled score-context features are both exactly zero. Historical player/minute/opportunity features remain present; this is not evidence that the model has no player information.
- CFB hurdle predictions are identity-blind under this permutation, consistent with its feature-based implementation. Score-context shuffling changes projections, but deterioration is not independently established by the interval.
- NFL opportunity pooling uses player share/rate lookups even though it has no one-hot identity encoder. Shuffled identities change forecasts and happen to lower aggregate MAE here; the game-clustered interval spans zero. No accuracy gain or new model is accepted.
- NBA hierarchical steal predictions use player identity; 91.9% of input player identities are known to its encoder. Shuffling increases MAE, with an exploratory positive delta interval. This supports sensitivity to that input, not overall predictive superiority.
- A market-shuffle control is unavailable because no verified historical market features exist in this cohort. No synthetic quotes were created.

The r3 source guard additionally verifies exact team/player evidence coverage and withholds uncertain availability at the unconditional research ingress. The original control result and r1 protocol remain preserved. The four control windows overlap the existing V24 confirmation data only as explicitly declared fixed-model diagnostics; none was reused to tune a model. The 79 sealed final-test games and other locked cohorts stay excluded.

Measured r3 controls: 15.181 CPU seconds, 15.187 wall seconds; no full-game simulations, production writes or promotions. Strict pregame evidence coverage remains zero.

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python scripts/controls-accuracy-v25.py
python -m unittest modeling.test_accuracy_v25_leakage modeling.test_accuracy_v25_evaluation modeling.test_accuracy_v25_recon
```
