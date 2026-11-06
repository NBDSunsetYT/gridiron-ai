# V20 research protocol and execution boundaries

This branch contains local research only. Production routes, models, database
records, wallet records, deployment settings and billing are unchanged.

The actual controller uses two single-threaded numerical workers, an exclusive
campaign lease, per-worker CPU/wall/RSS limits, a free-disk guard, compact
histograms and a cumulative 36,000-second active-time/CPU ceiling. It checkpoints
between bounded slices. A live detached process was verified; survival of cloud
environment shutdown is not guaranteed. Heartbeats distinguish observed active
time from unobserved suspension gaps. Unknown gaps consume a conservative budget
reservation and are not reported as measured computation.

## Selection and temporal integrity

The metadata-only protocol and its schedule amendment were frozen before V20
forecast grading. Previously examined V15–V19 game IDs are excluded. The separate
sealed final selections remain unopened. Point forecasts are fitted on at most
500 earlier completed games with a six-hour completion embargo. Full-game
coefficients are fitted before each cohort; role context can update from earlier
games before an event's 30-minute prediction cutoff. Current-game final rosters
and boxes do not select the pregame participant universe.

The owned historical play/box archives contain corrected statistics. Their
original publication times are not fully established. These experiments are
therefore **conditional corrected-history research**, even when the associated
injury report has a verified pregame timestamp. They do not establish prospective
accuracy or complete point-in-time reconstruction. Missing availability is never
converted to a healthy designation.

## Structural candidates

- Football passing-volume bridge: separately fitted team dropback/play forecasts
  change conditional state-level pass selection through a log-odds offset.
- Football quarterback mixtures: empirical-Bayes leader-continuity probabilities
  over earlier observed current-season quarterbacks. These are not probabilities
  that an injured quarterback will play. Verified explicit outs are excluded.
- NBA rebound hierarchy: Gamma-Poisson partial pooling of offensive/defensive
  rebounds per observed on-court rebound-opportunity exposure.
- NBA period-ending shots: no player rebound is awarded after a period-ending
  miss; every overtime begins with a new modeled tip. The opening-game winner
  controls the fourth-quarter entitlement; the opponent controls quarters two
  and three. See [NBA Rule 6](https://official.nba.com/rule-no-6-putting-ball-in-play-live-dead-ball/).
- Point projection comparisons: rolling averages, regularized regression,
  player/team partial pooling, gradient boosting and opportunity/efficiency heads.
- Additional hurdle hypothesis, registered after development window zero:
  predict nonzero opportunity, conditional volume and conditional efficiency
  separately. Fixed regularization; windows 1–3 are validation. This is a point
  projection model, not an independently generated set of complete games.

No candidate is promoted during this campaign. Counts distinguish unique
league/configuration combinations from repeated chronological windows and stat
heads. Paired uncertainty is clustered at the game level. Model uncertainty is
not the binomial Monte Carlo interval.

## Source repairs and remaining gaps

NBA historical reports use different filename conventions across periods. The
public `_05PM.pdf` document can exist when `_05_00PM.pdf` returns 403. The collector
tries documented/public formats and accepts actual PDFs only. It uses the later
of the report's printed issue time and original HTTP modification time, then
checks against cutoff. Exact earlier-known player IDs and team/matchup identities
are required; unresolved rows remain unresolved.

MAC availability document URLs can return HTML landing pages. The collector
follows the page's public PDF link and uses the PDF's pregame modification time,
not the landing page's current modification time. Local Eastern report dates are
matched against Eastern game dates. NFL provider modification dates are retained
with their provider confidence classification. Full original lineup and weather
forecast coverage remains incomplete.

[PropLine's documentation](https://prop-line.com/docs) was checked during V20.
It describes a 30-day historical event lookback on Hobby, with deeper tiers and
separate export entitlements. This is documentation evidence, not a successful
authenticated historical-price response. Most campaign games predate that range;
no plan change or purchase was made. No unverified thresholds, sportsbook prices,
DraftKings Predictions contracts or external probability weights are invented.
The existing integrations remain unchanged.

## Resume

Install the research-only requirements in the same checkpoint workspace, then:

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  python scripts/continue-overnight-v20.py --slice-seconds 1800
```

The supervisor skips completed stages and the controller skips completed cohort
jobs. Numerical changes require another revision; orchestration-only changes are
audited separately without overwriting the original execution specification.
Historical source/checkpoint artifacts are required in addition to source code.

Inspect status with `python scripts/research-overnight-v20.py --status` and generate
the current measured report with `python scripts/summarize-overnight-v20.py`.
