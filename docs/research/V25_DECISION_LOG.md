# V25 append-only research decisions

1. Start from the unchanged V24 tree on `research/accuracy-v25`. Preserve original forecasts, private artifacts, 79 sealed games and locked confirmation cohorts. Do not merge market-V18 numerical repairs into this branch.
2. Retain the existing 53-category tournament and model registry. Record conditional CFB receiving-TD / NBA rebound / NBA steal expected-value winners; reject unsupported passing improvements and keep probability heads separate.
3. Gate 1 is numerical baseline reproduction, not an accuracy-improvement experiment. No new fit, model selection, optimization, final-test evaluation, production change or migration is authorized by passing this audit alone.
4. The user explicitly requested both tasks be completed, with the earlier market-anchored task first. Its resumable 500-game audit remains active on its own branch. V25 source reconnaissance proceeds read-only while it runs.

5. Gate 1 passed by actual original-V24 inference replay: 34 traces / 24,043 rows, exact report digest equality, 1e-12 point tolerance; zero new fits, games or promotions. Three synthetic safeguard tests passed. The original training-code hash differences remain disclosed and are not erased. Stage 2 is not started while completing the earlier market task.
