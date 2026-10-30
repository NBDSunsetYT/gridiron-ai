# PWA release workflow verification

Use this guide to distinguish a deployed app check from the retained historical
verification reports. A localhost check does not establish that a production
HTTPS deployment works, and iPhone Chromium emulation does not establish a
physical Safari installation.

## Assistant record retrieval

`npx vitest run tests/assistant-workflow-records.test.ts` passed four checks:

- Actual temporary SQLite postings produce exact monthly withdrawals of 15,000
  cents and realized betting P/L of 7,500 cents through the assistant's ledger
  tool. Deposits and returned stakes are not counted as betting profit.
- Another owner's financial records and conversations remain inaccessible.
- Streamed answer text and ledger citations persist in the owner's conversation;
  the assistant does not change financial records.
- Missing credentials return 503, and a provider failure returns 502 without a
  fabricated assistant message.

The OpenAI transport is explicitly stubbed in this test. The ledger, ownership
checks, tool execution, streaming route and conversation database are real. This
is not a claim that an OpenAI API key is configured or that a live model answered.

## Full URL workflow

`scripts/smoke-pwa-workflow.mjs` tests a supplied local or production URL. Provision
two disposable, confirmed Supabase QA users first using authorized administrative
tooling. Do not send registration emails merely to execute this script. Each
identity must use an `example.test` address containing `qa`, and both financial
workspaces must be empty. Supply a private JSON file containing an array of
`{ "id": "...", "email": "...", "password": "..." }` account objects. Keep that
file outside the source checkout with mode 0600. Never use a personal account.

Set the following in a trusted local environment, keeping credential values out
of command arguments and terminal logs:

```text
BASE_URL=https://actual-deployed-app.example
QA_CREDENTIALS_FILE=/private/generated-qa-accounts.json
QA_ALLOW_SYNTHETIC_WRITES=1
PBP_NORMALIZED_CSV=/private/actual-normalized-historical-plays.csv
PBP_SOURCE=https://github.com/nflverse/nflverse-data/releases/tag/pbp
PBP_AS_OF=2023-11-30T00:00:00Z
PBP_EVENT_START=2023-12-01T01:15:00Z
```

The URL above is an example, not a deployed application address. Prepare the real
normalized play file using `modeling/nflverse_adapter.py` and the documented public
source. The default matchup is the historical DAL–SEA replay after the training
cutoff. No injury publication availability or prospective forecast is inferred
from the current historical file.

Run:

```sh
node scripts/smoke-pwa-workflow.mjs
```

The script verifies the standalone manifest/icons, actual Supabase login,
cross-owner isolation, deposits/withdrawals, pending exposure, a settlement,
source-labeled manual binary contract fees, saved prediction, separate paper
position, injury evidence states, a saved conversation, actual NFL schedule import,
and a fresh client's retrieval of remote records. When a real normalized play file
is supplied, it also fits actual historical evidence, runs 10,000 complete games,
checks correlated passing/receiving totals and saved result attestations, and
confirms that unsupported player-availability assumptions are rejected.

All financial, contract and injury mechanics fixtures are visibly **SYNTHETIC** in
the disposable account. Their prices and results are not actual DraftKings quotes
or real player injury news. Real historical NFL source imports and simulation
outputs are separately identified. No real wagers are placed.

The script attempts a live assistant query. A 503 is recorded as an unavailable
feature, not a successful conversational response. Omitting the historical play
file similarly records the simulation workflow as unavailable. The report's
`passed_with_explicit_unavailable_features` status must not be described as full
external integration success.

The script does not create or delete accounts, send messages, reset a database or
delete test records. Keep the QA accounts for a controlled deployment/restart
continuity check if needed. Afterwards delete only those verified disposable
owners through the existing authenticated account-deletion workflow, and remove
the generated private credential file. Never clean up real accounts.

The smoke script has passed syntax checking. Its production execution status must
come from the actual generated report at `docs/reports/pwa-production-workflow.json`
or the explicit `QA_REPORT_PATH`; this source guide is not a production pass.
