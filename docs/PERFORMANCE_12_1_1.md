# Production optimization — 12.1.1

This is an in-place performance release. NFL/CFB simulation counts, statistical
methods, random seeds, source fields, injury gates, validation and private Wallet
arithmetic are preserved. No paid resources, plan changes or keep-alive pings.

## Actual infrastructure and diagnosis

Vercel hosts the Next.js web service and private FastAPI `quant` service. Both NFL
and CFB calculations run there. Render hosts only the Python PropLine gateway;
it does not duplicate the quantitative simulation engine. There is one Supabase
15-minute public-research scheduler, no Vercel cron, and no Render compute worker.
Render's health check is the existing TCP check; `/health` stays dependency-free.

Current platform documentation assigns **4 hours Fluid Active CPU** to Vercel
Hobby, not Render. Render Free has 750 shared running-instance hours/month and
spins down after 15 idle minutes. Repeated polling can keep either workload busy,
but these are different billing metrics. No monthly remaining allowance was
modified or independently verified from a billing dashboard.

A Vercel log-count query showed 222 log events under `/cfb/public/prepare` in one
30-minute window. Detailed logs show many dependency-install lines per request:
this is **not 222 distinct requests**. One cold start installed Python dependencies
in 3.81 seconds. The platform manages that installation, not an application loop.
The release avoids unnecessary cold-path requests and excludes web/test assets
from the Python bundle. It does not claim to eliminate platform cold starts.

Scheduled CFB metadata refresh no longer calls the dashboard hydration path, which
prepared up to three unrelated cached games. The separate required prop-job queue
still refreshes and computes affected matchups.

Other bottlenecks: 10-second per-tab props polling; process-only board/preparation
caches; a single Python CFB prepared-game slot that evicts when switching games;
full-season Arrow allocation; repeated identical historical tuning transformations;
rebuilding conversion/context pools in simulated plays; copying a complete market
board just to return 500 rows; repeated schedule DB lookups before warm-memory reads.

The scheduled refresh also emitted PostgreSQL `57014` once. Existing RPC statistics
showed about 413 ms mean for the public prop writer, not a proven cause of that
particular timeout. Latest-run status now omits its unused result payload and has
a created-time index. A single timeout is not claimed permanently resolved merely
by that index; post-release logs and metrics must continue to be reviewed.

## Implemented caches and coordination

`gridiron_performance_cache` reuses existing `shared_nfl_cache` and private lease
metadata. No duplicate research table, user table or history migration is created.
Only a server capability can read/write this namespace; direct anonymous reads are
excluded by the existing policies. Generation-fenced leases coalesce cold-instance
work. Failed/expired producers cannot overwrite a newer cache value. A failed
refresh never extends freshness or deletes the prior saved research.

Public-only namespaces and TTLs:

| Namespace | TTL | Identity |
| --- | --- | --- |
| CFB preparation lookup | 10 minutes | implementation, exact game/teams/kickoff/season/week; returned input hash retained |
| PropLine board page | 60 seconds | implementation, sport, exact cursor |
| Calculated prop page | 20 seconds | implementation, sport, cursor, complete quote/availability input hash |
| CFB provider configuration status | 5 minutes | provider implementation |
| Published CFB schedule | 60 seconds | source implementation and exact date |

A preparation lookup cannot know a corrected upstream asset hash before checking
the source. Its bounded 10-minute validation window is unchanged; prediction and
simulation storage still require the actual verified input hash. Completed runs
continue using existing durable compact storage and input-change invalidation.
Injury/weather TTLs and original model freshness guards are not relaxed.

Cache payloads are checksummed, gzip level 1, at most 16 MB raw/500 KB compressed.
A process mirror is capped at 16 MB. Shared entries are capped at 64; eviction
applies only to this disposable namespace, never user research or prediction
history. SQL leases last at most 5 minutes; failures back off 30 seconds. Waits are
bounded. Coordination outages do not launch duplicate heavy work as a fallback.

Browser GET boards coalesce in-flight requests and share public-only responses
through BroadcastChannel with Web Locks where supported. POST/private responses
are excluded. Polling pauses while hidden, is 15 seconds while pending, 60 seconds
when settled, and backs off to 120 seconds after failures. Loaded pages refresh in
rotation. Navigation aborts obsolete browser requests. View sorting is memoized.

## Numerically equivalent Python work

Prior/window tuning reuses integer sufficient statistics across prior strengths.
NFL/CFB evidence reuses static play-pool lookups and conversion/start CDFs without
changing random draws or probabilities. CFB Arrow batches preserve physical row
order, selection predicates and every model input. A bounded four-game prepared
cache replaces the one-slot cache. Render clones only the requested market page,
counts categories in a single pass and reuses verified timestamp windows while
still rejecting expired quotes.

Original source implementations are retained in `tests/fixtures/performance-originals`
for reproducible CPU/equivalence benchmarks. Fixtures are clearly labeled synthetic
and excluded from production deployment. Public CFB normalization can additionally
be tested with an actual SportsDataverse parquet asset. Benchmarks assert identical
outcomes and distributions before reporting savings.

## Monitoring and operations

`GET /api/internal/performance` requires the existing server-ingest Bearer
capability. Python/Render `GET /metrics` requires each service's existing internal
authorization. Neither returns credentials, personal data, request bodies or query
strings. Metrics are bounded process-local counters: requests, errors, latest-128
p95/average latency, CPU and memory, cache/lease events, DB/provider requests.
Python guarded work measures actual thread CPU. Node span CPU includes concurrent
work, so overlapping spans must not be summed as billed CPU. Process snapshots are
not a durable cross-instance billing history; native provider metrics complement
them. No new external telemetry subscription is required.

## Recovery

`checkpoint/pre-performance-20261103` preserves the original source. Roll back the
application first if necessary; the additive RPC/index may remain. Do not delete
saved research, user tables, financial rows or immutable versions. Disposable cache
entries are not backups or historical prediction records. Original encrypted
recovery material remains untouched. Existing authentication and per-user RLS stay
in force.

See `docs/reports/performance-*` for actual benchmarks, verification and deployment
results. Local CPU reduction is not a measured monthly billing reduction. Traffic,
cold-start frequency, cache warmth and actual model changes determine hosting use.

## Production delivery

The release is live at https://gridiron-ai-gray.vercel.app. Vercel deployment
`dpl_8RkAogr9tq9o9TRyoWojmXTmPhsq` is READY with source
`3e91fae793754c5dbb6b1a91a828e15937217458`. Render deployment
`dep-dbkk14ou01pc73dgvkg0` is live with gateway source
`94f4a10e79f6ad0efa0728cbeefddf761d9e08d6`. The final preview
`dpl_3abTiiQ9pjrd8hhxvYKXk7rcYu8p` passed health/dependency and manifest checks.
Production-only bridge secrets were kept out of Preview.

Verification: 720 TypeScript tests, 191 full-suite Python tests, 17 focused Python
release checks, 12 PostgreSQL suites, 32 desktop/iPhone-viewport browser checks,
five live performance checks, six live automatic-research workflow checks and
15 live PWA checks passed. Four concurrent readers per sport preserved identical
estimates for identical model inputs. Private Wallet and operator endpoints
rejected guests, and actual saved research history remained retrievable.
No personal financial records were written by the production acceptance scripts.
The first NFL response was stale/pending; automatic refresh completed and the
subsequent complete workflow passed without clicking an analysis button.

Matched local CPU measurements for 100,000 complete games: NFL 93.62 → 33.41 s;
CFB 92.62 → 31.63 s. Chronological CDF fitting fell 82.3%, and the warm Render
page-copy workload fell 93.8%. These use labeled synthetic mechanical fixtures
and exact output equality; they are not model-accuracy or total-billing claims.
Real CFB normalization retained identical output and reduced isolated peak RSS
244.8 → 221.6 MB. That isolated cold normalization was slightly slower, while
warm normalization was faster.

Live response latency depends heavily on cache warmth and source readiness. The
first two measured app spans took about 7.47 and 4.88 s; a subsequent warm app span
was 31 ms. These are cold-versus-warm observations, not a controlled before/after
release comparison. Existing cold-start installation overhead remains possible.
No paid plan was enabled, quotas were not increased, and prior consumed CPU was
not restored. Monthly billed savings require an ongoing observation window.
The brief verification window did not include observing the next 15-minute cron
tick; the metadata-only cron change is regression-tested separately.
