# V25 append-only research decisions

1. Start from the unchanged V24 tree on `research/accuracy-v25`. Preserve original forecasts, private artifacts, 79 sealed games and locked confirmation cohorts. Do not merge market-V18 numerical repairs into this branch.
2. Retain the existing 53-category tournament and model registry. Record conditional CFB receiving-TD / NBA rebound / NBA steal expected-value winners; reject unsupported passing improvements and keep probability heads separate.
3. Gate 1 is numerical baseline reproduction, not an accuracy-improvement experiment. No new fit, model selection, optimization, final-test evaluation, production change or migration is authorized by passing this audit alone.
4. The user explicitly requested both tasks be completed, with the earlier market-anchored task first. Its resumable 500-game audit remains active on its own branch. V25 source reconnaissance proceeds read-only while it runs.

5. Gate 1 passed by actual original-V24 inference replay: 34 traces / 24,043 rows, exact report digest equality, 1e-12 point tolerance; zero new fits, games or promotions. Three synthetic safeguard tests passed. The original training-code hash differences remain disclosed and are not erased. Stage 2 is not started while completing the earlier market task.

6. Clarified replay scope: 39 focused software tests passed, but numerical inference was rerun only for the original six-category / 34-trace baseline. All-category metric and interval regeneration belongs to the next harness stage and is not claimed complete.

7. Gate 2 r2 passed: 320 original model/window traces across 52 categories reproduced point estimates, intervals and metrics. CFB targets is explicitly unsupported. Eight golden/isolation/reconstruction tests passed. Original frozen model/report/cohort editions are bound by hashes. No new model fit, independent game, strict forecast or production promotion. The first r1 replay remains preserved.

8. Parallel work was limited to bounded, read-only frozen inference/scoring and safeguards while the primary market audit used its two local workers. No V25 model training or optimization ran. Gate 3 r2 passed 18 software tests and 12 actual fixed-model controls; all four shifted-future histories were rejected. The NBA steal identity ablation is sensitive; other effects are absent or uncertain as documented. Historical market control is unavailable, not fabricated. No candidate was selected from these exposed diagnostics.
