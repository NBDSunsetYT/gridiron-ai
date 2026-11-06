# Market V18 research checkpoint

This branch is an incomplete Stage 1 checkpoint. The user supplied a new V25 directive while its 500-matchup audit was running. The two local workers were stopped and all completed forecasts were retained. No later stage was started and no model was promoted.

The exact counts and untuned regression deltas are in [the checkpoint](reports/market-v18-checkpoint.json). They are exposed historical regression results, not independent forecasting accuracy. Gate 1 remains closed until all 500 original matchups complete and the required commands pass. Stages 2–4 have not been implemented on this branch. Fitted blend weights, verified CLV samples and closing-price metrics are null/unavailable.

Implemented repairs cover current-opponent/league-prior pools, empirical shrinkage, unified late-clock handling, stopped-clock plays, source-fitted tempo, typed restarts, fitted regulation conversion decisions, observed return-touchdown transitions, participant depth ordering/caps and position priors when source positions exist. Original V15.0/V15.1 coefficients and families are migrated without refitting. The old V15.1 source remains loadable with identical seeded results. New artifacts use `football-market-candidate-18.0.0`; prior artifacts are not overwritten. Missing rates remain null.

The public NFL schedule dictionary does not verify book, capture time or closing status. Those unverified spread columns cannot satisfy the requested closing-line gate. No market price was invented.

## Resume only when this research task is reactivated

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python scripts/market-v18-gate1.py --tests
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python scripts/market-v18-workers.py
python scripts/market-v18-gate1.py
```

Requires the preserved authorized artifact workspace. Registering over an existing protocol or altering its numeric source is forbidden; use a new revision if needed. All 500 games retain original seeds and 10,000 full-game trials each. The coordinator uses at most two local processes with CPU, wall-time, memory and disk bounds. It does not use Vercel, Render or production databases.

Known limitations remain: source publication editions and historical lineups/injuries are incomplete; CFB position priors and some return/clock flags are unavailable; migrated legacy models retain their original overtime approximation. New fitted spike classes require explicit overtime treatment before use outside the migrated audit. No strict pregame or production eligibility is claimed.
