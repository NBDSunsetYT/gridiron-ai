# V26 real prospective numerical reference capture — revision 1

Captured at **2026-11-06 23:33:43 UTC**, before the first target's 00:00 UTC tipoff. The inputs comprise **59 verified completed-game sources** and **12 current rosters** for six real NFL/CFB/NBA matchups. Source URLs, content hashes and capture times are stored with the [immutable derived snapshot](V26_PROSPECTIVE_R1.json.gz). Raw publisher responses remain private.

There are **102 player references**, with four known unavailable players explicitly withheld. Current official NBA status, current NFL official report and unconfirmed college availability remain distinct. No player is called healthy merely because an injury row is absent. The current NFL article has 142 parseable facts and one malformed item explicitly withheld; its original strict parser still fails closed if no diagnostic error sink is supplied.

These are the original simple rolling references for future measurement. They are **conditional on availability and recent role continuing**, not independently validated winners, joint-game simulations, or production forecasts. No target outcomes have been read. No Monte Carlo game count is attached to these arithmetic references.

| Event (UTC) | Conditional score reference (away–home) | Selected player reference | Availability / limitations |
|---|---|---|---|
| NBA Boston at Charlotte, Nov 7 00:00 | 109.9–101.0 | Payton Pritchard: 26.8 minutes, 11.0 points, 3.2 rebounds, 4.0 assists | Officially Available; role/rotation conditional |
| NBA Portland at LA Lakers, Nov 7 03:00 | 114.5–115.5 | Walker Kessler: 29.8 minutes, 13.4 points, 12.0 rebounds, 1.2 assists | Officially Available; role/rotation conditional |
| NFL NY Jets at Kansas City, Nov 8 18:00 | 19.7–23.0 | Patrick Mahomes: 31.6 attempts / 245.8 passing yards; Geno Smith: 27.4 / 226.0 | No confirmed full active lineup; Garrett Wilson Out is explicitly excluded |
| NFL Tampa Bay at Chicago, Nov 9 01:20 | 22.3–19.7 | Caleb Williams: 34.33 attempts / 286.67 yards; Jalon Daniels: 31.67 / 167.0 | Appearance-conditioned references use only three observed games for these QBs; starter/replacement uncertainty remains |
| CFB Alabama at LSU, Nov 7 20:30 | 23.5–30.8 | Keelon Russell: 27.6 attempts / 258.6 yards; Sam Leavitt: 32.6 / 288.2 | College availability/participation incomplete at this revision |
| CFB Texas at Missouri, Nov 7 17:00 | 22.8–23.4 | Arch Manning: 24.0 attempts / 213.2 yards; Austin Simmons: 34.4 / 260.0 | College availability/participation incomplete at this revision |

Score references average the team's previous scoring mean with its opponent's previous points-allowed mean. They are comparison baselines. Full-game forecast fields, win/spread/total probabilities and qualified prediction intervals remain **null** because the full-game qualification requirements have not passed. Five recent observations do not justify an invented 90% prediction interval; historical ranges are labeled descriptive ranges instead.

## Confirmed structural issue to test next

Independent appearance-only averages are not additive team budgets. For example, the original Boston player-minute references sum to **258.85 minutes**; different players have different appearance denominators. LSU passing references similarly include QB averages over unequal appearance counts. These are detected defects in combining such marginal references, not proof that any proposed replacement is more accurate.

The next bounded experiment will use a common calendar-game denominator only where official team opportunity totals reconcile. An absent player can receive a historical zero only when the complete published opportunity table proves the team's opportunities were accounted for. Unknown availability is not converted to healthy, and injured-player volume will not be arbitrarily reassigned. Keep this revision unchanged, compare the alternative separately, and report high-volume and low-volume errors as well as aggregate error.

## Forecast qualification

New strictly qualified full-game forecasts: **0**. New independent accuracy measurements: **0**, because target games have not finished. All existing V24/V25 production champions are retained. Every game snapshot contains its exact blocker list: missing supported full lineups/restrictions, model-bound mechanics and independent probability validation; CFB additionally lacks administrative clock/pace certification.

Mode B has conditional numerical references. Mode A stays withheld. Mode C remains marketless: no invented prop thresholds, executable prices, fees, settlement rules, closing observations or CLV. No research candidate was promoted.

Reproduce only in the preserved research workspace:

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python scripts/v26-capture.py
# Forecast capture is prospective: it refuses to backdate after kickoff.
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python scripts/v26-forecast.py
python -m unittest modeling.test_evidence_recovery_v26 modeling.test_prospective_inputs_v26
```

An existing immutable capture is not overwritten. After kickoff, use the saved forecast for grading; do not regenerate it using later inputs.
