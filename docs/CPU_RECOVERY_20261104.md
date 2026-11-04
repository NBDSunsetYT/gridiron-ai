# Vercel CPU recovery — 4 November 2026

The application now separates web reads from model execution. Vercel serves cached research and admits durable work requests. NFL, CFB and NBA fitting, full-game simulation, historical preparation and private simulation dispatch are blocked on Vercel, including when a worker flag is accidentally set there. Numerical engine code, trial counts, injury safeguards and saved forecasts are unchanged.

## Confirmed causes and evidence

The previous `vercel.json` deployed a Next service **and** a Python FastAPI quantitative service with an internal binding. The existing free Render service is the PropLine data gateway, not the simulation worker. Fluid Active CPU belongs to Vercel in this architecture; Render has different metrics and billing.

CFB dashboard hydration called `/cfb/public/prepare` to discover whether saved analyses were usable. A cold preparation can reload historical plays and fit models. Prop-board reads scheduled historical preparation and simulation through `after()`. Probability jobs held requests open, repeatedly recalculating every five seconds. Private dispatch deliberately kept both Node and Python invocations alive. The signed scheduler ran every 15 minutes and nested source refresh, prop research, model audits and learning work. A signed-in browser pipeline could independently run those jobs. NBA preparation could precede the cached-simulation lookup.

The inspected recent Vercel log window contained 39 log events for `/cfb/public/prop-history`, 37 for `/cfb/public/prepare`, 37 for `/health`, and 2 for `/api/nfl/refresh`. These are **log-event counts**, not invocation counts or CPU measurements. Exact historic per-endpoint CPU attribution was unavailable: the observability query connector returned HTTP 400, and Hobby runtime logs retain only one hour. No invented endpoint CPU totals are reported.

Render CPU samples for the existing gateway were roughly 0.002–0.0037 cores. Its HTTP-count metric returned no series. These measurements do not establish Vercel savings or remaining quotas.

## Implemented safeguards

- Removed the quantitative service and internal binding from Vercel. Python runtime/dependency files are excluded from its deployment, while remaining in Git for local/Render workers.
- Added hosting-policy guards to Python execution and every relevant Next quantitative dispatch path. Request-bound model execution is never permitted on Vercel.
- Added a capability-protected, private durable queue in the existing Supabase project. It extends the existing daily budget table and leaves financial records, private RLS and forecast histories unchanged.
- Queue IDs include the full validated task, sport, event, count, exact selection and queue implementation version. Verified model-result caches retain their existing input/model/source/assumption identities. The worker rechecks current evidence before deciding whether a cached simulation remains valid.
- Global concurrency is **one**, with at most **6 admitted tasks, 100,000 reserved game trials and 1,800 worst-case execution seconds per UTC day**. A task is capped at 300 seconds. Reservations remain charged after a crash. Expired leases and late completions are fenced. Retries back off exponentially and stop after five attempts.
- Missing forecasts queue automatically. Browser reloads coalesce requests; they do not launch models. Ready histograms may still be evaluated cheaply on the web. Raw probabilities are not relabeled calibrated.
- Added persistent CFB prepared-input metadata and a compact saved-run index so cold web instances can retrieve local-worker results without preparing models again. NBA cached-run pointers refresh only after current inputs are verified.
- Removed automatic prop execution and repeated selection-snapshot work from visitor responses. Shared refresh and learning work belongs to the controlled worker. Private inputs remain in their existing authenticated queues.
- Bounded, visibility-aware polling replaces five-second matchup polling. Failure backoff, finite attempts, cancellation on unmount and request coalescing limit traffic. Private browser pipelines stop scheduling on cache-only hosting.
- Immutable research objects have a bounded, checksum-keyed server cache, single-flight loading and per-caller copies. Failed reads never replace good evidence. Public dashboard CDN headers are explicit; private records remain uncached.
- Health checks on cache-only hosting no longer wake a quantitative service. Operator metrics include queue admission, daily reservations, measured worker CPU, cache events and process-local CPU/latency diagnostics. Concurrent process spans are not presented as billed CPU.

## Measured benchmark

`node --import tsx scripts/benchmark-cpu-cache.ts` used the same real archived 206,446-byte CFB forecast for 400 reads, with no simulations or provider calls.

| Local immutable-object read workload | Before | After |
|---|---:|---:|
| CPU | 722.532 ms | 442.317 ms |
| Wall time | 662.612 ms | 434.014 ms |
| Object loads/decompressions | 400 | 1 |

This is a **38.8% codec CPU reduction** and identical probability checksum, not a claim of 38.8% lower total hosting CPU. Queue tests also prove 50 simultaneous/repeated identical submissions make one enqueue RPC. Cold-cache CFB tests prove saved-result page reads perform zero Python prepare/simulation requests. Production billed CPU before/after cannot be measured while the team is paused. Removing Vercel simulation execution structurally removes that workload from future Vercel requests; the total billing reduction needs a comparable post-resume traffic window.

## Controlled worker

```sh
python scripts/compute-worker.py --dry-run
python scripts/compute-worker.py --refresh --max-jobs 2 --cpu-seconds 300 --wall-seconds 600
```

Supply the existing server credentials through a protected operator environment: `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY`, `GRIDIRON_PUBLIC_INGEST_TOKEN`, `SIMULATION_SERVICE_TOKEN`, and the existing data-gateway configuration when needed. Never put keys in command arguments, browser code, Git or logs. The worker starts a private loopback Python service, uses one process group per task, one numerical thread, OS CPU limits, and a supervisor that terminates the entire group on wall/CPU exhaustion. It saves compact aggregates through the existing storage paths. It creates no paid resource and does not run persistently unless an operator schedules it.

`--refresh` admits one shared maintenance task, including at most one automatic prop-research game and the existing bounded learning audit. It does not run all matchups. User-owned jobs retain their original ownership and require a separately authenticated worker/session; no user JWT is stored in a shared queue or invented by a scheduler.

The existing database cron was reversibly suspended while the deployment is paused. Its replacement web endpoint only queues maintenance. Do not resume the old CPU-heavy deployment. After the optimized deployment is selected and service is available, verify cached reads and queue admission, start a controlled worker if new forecasts are needed, then restore the existing cron at a reduced cadence. An offline worker means new requests remain queued; the UI must not claim they completed.

## Verification and recovery

The additive migration is `supabase/migrations/20261104211620_bounded_compute_queue.sql`. Production schema inspection confirmed the old `games` counter remains, RLS is enabled, and both anonymous and authenticated direct queue reads are denied. An isolated completed test record was inserted, updated and retrieved over separate production database calls, then removed. It was never eligible for execution. Local Postgres tests cover positive/negative capability authentication, persistence, deduplication, concurrency, fencing, backoff and budgets. Existing user/financial records were not modified.

Recovery checkpoint: local branch `checkpoint/cpu-pause-20261104` at `d52a4f81eeceef095ff5ea540e6430e5ff5c3896`. The migration is additive; reverting application code does not require deleting its queue or budget columns. Never reset the database or restore the old web simulation topology merely to roll back UI changes. Keep the compute boundary and paused schedule in place during recovery.

Test and deployment receipts are recorded in the delivery report. Production HTTP tests remain subject to Vercel's quota pause; a successful build alone is not serving recovery. No plan, payment setting or paid resource was changed.
