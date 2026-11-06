# V25 drift audit

V25 starts from the exact V24 source tree, with no V18 engine repairs or V25 experimental models merged. Model and source hashes are verified before unpickling owned private artifacts. Inherited artifact checks are read-only; baseline outputs, registry records, protected cohorts, financial records and production configuration must remain unchanged.

## Reproduction policy

Reconstruct the existing feature pipeline, compare each feature-input hash, load only the original checksum-addressed model, use the frozen distribution seed/draw count, and compare point estimates and prediction intervals at a declared 1e-12 numerical tolerance. Recompute the original metrics with the original grading labels after prediction, without refitting. Missing models/sources and numerical drift are failures; do not fabricate replacements or tune a repair to obtain agreement.

The original V24 replay covered 34 model/window traces and 24,043 forecast rows across six categories. V25 audits that baseline and expands read-only reconstruction to the primary leaderboard's supported categories. Missing original category fits retain their insufficient-evidence status. The expanded check is not a new independent forecasting test.

Some original fit protocol code hashes predate known reporting-only source corrections. These differences must be listed, not silently ignored or described as identical fitting replay. The point/model/feature/distribution checks determine whether the original saved inference can actually be reproduced on this dependency environment. No claim of original training reproducibility is made without the original fitting code edition.

## Actual execution

Gate 1 passed. The original V24 replay executed again: **34 frozen model/window traces, 24,043 forecast rows, six categories** (NFL passing yards/moneyline, CFB passing yards, NBA minutes/rebounds/points). All reconstructed input hashes matched; point forecasts matched the original 1e-12 tolerance and the entire replay report matched exactly. Original distribution seed 240241 and 128 marginal draws were reused. These draws are not full-game Monte Carlo trials.

Original and replay report digest: `f4b27b78be0a5f8701d8e06568c01832fa1b38f20660c5e25010e176dc3b6991`.

The preflight verified 5,248 source/model/forecast files and 6,526 inherited artifact files with zero missing/checksum failures. All 161 protected IDs remain excluded (including the 79 sealed final-test games); no protected final outcomes were opened. Original public/private replay JSON and reliability image hashes remained unchanged. The 100-head bank retains its V24 checksum.

Twenty superseded fit-code hash entries concern three files across the eight original protocols: `completion/selection.py` (7), `scripts/complete-models-v24.py` (7), and `completion/joint.py` (6). Inference reproduction passed despite these known later revisions. This does **not** prove that every original training run can be re-created from the latest source. The full list of original/current hashes is in `V25_BASELINE_REPLAY.json`.

Measured replay: 31.433 CPU seconds, 31.432 wall seconds, peak RSS 1076636 KiB. No model was refit, no new independent game was tested, no new full-game simulation ran, and no accuracy improvement is claimed.

Reproduce in the preserved authorized artifact workspace:

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python scripts/recon-accuracy-v25.py
python -m unittest modeling.test_accuracy_v25_recon
```

The immutable V25 `preflight.json` and `protocol.json` are part of the private checkpoint; they bind original source/model editions and code. They and the original V24 fitted artifacts must be restored for reproduction. The script refuses missing, changed or mismatched inputs. No fitted private artifacts, raw datasets or credentials are published. The separate market-V18 audit continues first and is not counted as V24 baseline evidence.
