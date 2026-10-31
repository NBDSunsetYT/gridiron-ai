> Historical staging report. Superseded by the live [9.0 integration](PROPLINE_V9.md). Original evidence below is preserved.

# PropLine replacement — staged, not deployed

Production remains version8.0.0. This feature branch prepares PropLine as the primary NFL/CFB sportsbook-prop source. It must not be merged/deployed as a verified working feed until an operator-owned key produces successful real boards on Render. No database migrations, user-data edits, production environment changes or purchases were made.

## Verified current documentation and actual HTTP responses

Official https://prop-line.com/docs and https://prop-line.com/llms-full.txt both returned HTTP200. They advertise Free:1,000requests/day, all sports and current odds; history/results and some derived research endpoints are redacted. Header authentication is `X-API-Key`. Daily reset is00:00UTC, burst5requests/second with10token burst. One bulk odds request per sport avoids per-game polling. Documented football keys are `football_nfl` and `football_ncaaf`; NFL/NCAAF markets include passing, rushing, receiving, receptions and touchdowns. DraftKings denotes Sportsbook; this is not a DraftKings Predictions partner feed. Coverage documentation does not prove today's book/market inventory.

Actual unauthenticated `/v1/sports` returned401 `missing_api_key`. The provider explicitly publishes a demo key for read-only testing. Two bounded NFL/CFB bulk-board probes with that demo credential returned429 `daily_limit_exceeded`, observedtierFree, dailycap1,000 andremaining0. No key or raw error body is committed. No successful event, player, line, price or book response was observed. The demo is shared and is never used by production code. No upgrade link was followed or purchase started.

Both https://api.parlay-api.com/player-props-api and the API root returned403 `error code:1010`; the marketing root also returned403. The response does not establish subscription requirements, endpoint schema, API authentication or sport coverage. No private API, guessed path, alternate IP or access-control bypass was attempted. ParlayAPI is disabled pending accessible official documentation and credentialed real responses. The fallback selector supports only validated same-sport current sportsbook rows and never replaces prices with unrelated exchanges.

Authorized Render discovery still returns zero services in the previously authorized workspace. The earlier free-service creation block required payment-information verification. This task did not retry creating a service or initiate charges. No operator-owned PropLine or ParlayAPI key has been verified. Provider keys belong only in Render environment configuration; the frontend/Vercel receives only the separate authenticated gateway URL/token.

## Implemented foundation

- Render-only PropLine bulk-board client with header credentials, no redirects forwarding credentials, bounded bodies, fixed official host, daily/request quota controls and five-minute server cache. Upstream429/reset halts further requests across both sports in that worker. Provider quotas remain authoritative across independent workers/redeployments; local counters are not a distributed durable quota guarantee.
- Current supported rows require exact provider sport/event/player-name fields, finite American prices, exact threshold, recent provider observation and selection still present in latest delivery. Null touchdown thresholds remain null. DraftKings Sportsbook sorts first. Exchange/DFS books are excluded. Book publication time, settlement rules, fees, calibration and EV remain unknown, not zero.
- `/data/props/NFL` and `/data/props/CFB` authenticated gateway routes, safe same-origin frontend bridge, and a staged sport-specific primary interface. The existing Hub is intentionally not switched to this component until successful live verification; current production behavior stays intact. Legacy BALLDONTLIE routes remain for compatibility; DraftKings Predictions remains separate.
- Strict complete-game histogram comparison primitive rejects cross-sport/event/player/kickoff joins and missing distributions; pushes are separate. It is not yet wired to verified real provider IDs and persisted simulations. No arbitrary name joins or synthetic probability outputs.

## Still required before release

1. Resolve Render's existing account setup and run the gateway on its explicit free tier; no paid tier is authorized.
2. Set an operator-owned `PROPLINE_API_KEY` in Render only and verify actual NFL/CFB boards and entitlement. Never paste keys into chat or Git.
3. Verify ParlayAPI documentation, free-tier eligibility, authentication and actual schema before implementing its live reader. Framework fixture tests do not establish live fallback access.
4. Finish verified provider-to-model crosswalks and UI regression tests from actual response shapes. Do not promote vendor projections as independent model estimates.
5. Add reviewed additive Supabase provider constraints and guarded cache writes after live shape verification; existing public research reserve is already capacity-blocked. No cache is currently claimed saved in Supabase. No guard is waived and no existing records are deleted.
6. Run real-response integration, mobile regression and production acceptance tests before deploying.

This is a concrete staged implementation, not a verified live integration or a completed replacement deployment.
