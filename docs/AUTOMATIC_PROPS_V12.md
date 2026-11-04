# Automatic player-prop research — version 12

The existing NFL/CFB PropLine screen now starts public server-side analysis when
it opens. Price buttons open already calculated evidence; no manual probability
request is required. The existing advanced 10k/50k/100k engine remains available.

## Evidence hierarchy

1. Reuse a verified current complete-game distribution. If none exists and the
   unchanged background compute allowance permits it, run 10,000 complete games.
2. Distribution candidates (Poisson, negative binomial, lognormal and empirical
   benchmark) have an expanding chronological evaluation and paired block
   bootstrap gate in `modeling/prop_candidates.py`. No candidate is approved by
   fitting alone. No prospectively validated production artifact is currently
   configured, so this tier is not claimed operational.
3. Use supported published historical player-game totals as a clearly labeled
   empirical research estimate. NFL uses nflverse weekly totals and exact
   roster/ESPN crosswalks. CFB uses complete published SportsDataverse game-stat
   events, including overtime and NCAA sack rushing. It does not sum the
   simulator's filtered regulation training pool. Five observations are required,
   and the most recent twelve are retained. Missing stats are never guessed zero.

Historical estimates are conditional on recorded participation (CFB on observed
usage). They are **not** calibrated next-game forecasts. No fitted opponent,
roster-change or weather effect is invented. Known restricted availability
withholds the affected player when no calibrated availability mixture exists.
Intervals describe historical frequency sampling uncertainty; full structural
uncertainty remains unquantified. Simulation intervals and MCSE are displayed
only for actual complete simulated games. Price break-even is separate.

## Storage and coordination

The additive migration adds two private operational research tables and one
capability-gated RPC. Existing private financial/user tables are unchanged.
Jobs are keyed by sport and exact ESPN event, with earliest kickoff priority,
atomic SKIP LOCKED claims, five-minute leases, changed-input fencing, retry
backoff and immutable result references. Model-input identities exclude market
prices. Current inputs are rechecked on a bounded fifteen-minute schedule.

Each game stores compact distributions, source/model/input versions and
assumptions through the existing immutable research object store. Exact loaded
selection/threshold estimates receive separate immutable snapshot references.
Saved user combination revisions retain their history and update only research;
actual wagers and accounting records are never edited by research jobs.

The existing authenticated football refresh invokes this queue. Page polling
also resumes work. Polling does not run computation on the phone. Server board
responses are briefly cached and a bounded number of source pages load
without user interaction. Additional pagination retains automatic analysis.

`GRIDIRON_AUTO_PROPS=0` disables the new automatic public-board path without
removing historical data or changing the existing advanced probability API.
Rollback the application deployment first if needed; retain the additive queue
and version tables. Do not drop them once research has been saved.

## External limitations

PropLine supplies sportsbook references. DraftKings Sportsbook is never labeled
DraftKings Predictions. Missing exact settlement/fees preclude fee-aware value.
Authorized DraftKings Predictions access remains unavailable. Atlas routing and
R2 archives remain opt-in and unconfigured under the existing access limitations.
General OpenAI chat needs a server-side credential; deterministic evidence and
account reports remain separate. No physical iPhone install is claimed.

See `docs/reports/automatic-props-v12*.json` for actual verification results.

## Production delivery and acceptance

Live app: https://gridiron-ai-gray.vercel.app/#props

Deployment `dpl_5awcdu21hw5DWgn8Tq5fGGQcWJcg` is READY from runtime source
commit `ebdc0fd51b3b8e5f172d1409ad2d64770ccf5700`. All 284 runtime source
files matched the reviewed Git commit. Render's existing private PropLine
bridge and all existing secrets were preserved. The Python quantitative service
continues running as its existing private Vercel service; it was not relocated.

Actual deployed GET-only tests found 199 supported NFL empirical estimates on
one 500-row page and 28 CFB full-game estimates on a 46-row page. These are
point-in-time coverage counts, not accuracy. Unsupported players, insufficient
cohorts, uncertain availability and already-started games remain explicit.
A real iPhone-sized browser opened Props, saw computed percentages without any
analysis POST, opened existing evidence, reloaded and retrieved it again.
The actual database retained five public distribution versions and seven exact
selection snapshots during verification. No financial record was created.

Passed: 701 TypeScript tests, 180 full Python tests plus four newly added tests
(184 distinct across runs), 11 PostgreSQL suites, automatic desktop/mobile tests,
14 final legacy browser regressions, and actual deployed 5 workflow + 15 PWA
checks. Separate PWA regressions also passed. No physical iPhone test occurred.
Initial test-only issues (a hardcoded old release assertion and a Strict Mode
fixture timing assumption) were corrected and rerun. An isolated production
build resolved a concurrent dev/build output collision; the cloud build passed.

Open the link in iPhone Safari, then Share → Add to Home Screen → Add.
Private API responses remain excluded from service-worker caching. Source ZIPs
are source only; the hosted backend and persistent database execute remotely.

Remaining limitations: no approved prospective calibrator/player-distribution
artifact; current statistical estimates do not fully quantify injury, weather,
matchup or structural uncertainty. Daily complete-game capacity was exhausted
during verification, so hosted runs were reused and empirical fallbacks were
verified rather than bypassing the guard. Exact DraftKings Predictions access,
Atlas policy approval, R2 configuration and a general OpenAI credential are
still unavailable. Separate sportsbook prices are never relabeled.
