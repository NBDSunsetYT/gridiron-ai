# Exact player-prop research, version 6

Version 11 storage update: new runs replace the ordered `playerSamples` described
below with per-replicate `playerHistograms`. Exact threshold counts and parameter
intervals are preserved; marginal frequencies do not establish joint outcomes.
The legacy binary encoding remains readable. See `docs/GRIDIRON_V11.md`.

The play-by-play engine continues to simulate coherent full NFL games. Its player
histograms use **exact integer values**, not chart buckets. Every player's
statistic histogram reconciles the base simulation count, including explicitly
recorded zero-event games. The marker is `exact_integer_frequency_v1`.

`touchdowns` is derived within each simulated game as rushing plus receiving
touchdowns. Passing touchdowns never count as scorer touchdowns. The engine does
not attribute defensive or kick/punt-return touchdowns to players. Contracts that
include those events cannot be valued as if this narrower statistic covered the
full settlement rule. Full-game distributions include overtime; regulation-only,
quarter and half contracts are unsupported by this representation.

## Reusing a game for many exact thresholds

`prop_research.evaluate_exact_player_distribution(result, definition, outcome)`
validates a trusted saved result, exact player/statistic, finite threshold,
over/under direction, and explicit equality settlement. It reports separate YES,
NO and push counts, raw simulation probability, Wilson sampling interval and
Monte Carlo SE. A raw probability is not relabeled calibrated. Missing player
evidence is unavailable, not an inferred zero. Explicitly withheld players remain
withheld.

## Parameter sensitivity is separate from sampling error

The automatic pipeline retains its fixed ten whole-historical-game Bayesian
bootstrap replicates, with 100 coherent simulated games per replicate. Increasing
the main game count does not increase this parameter sample or make its interval
shrink automatically. These intervals include finite inner simulation noise; they
do not cover every structural, roster or injury assumption and have no validated
predictive coverage.

`uncertainty.parameterBootstrap.playerSamples` provides bounded shared player
outcomes using `gzip_base64_int32le_shared_player_stats_v1`. Shape is
`[replicates, gamesPerReplicate, playerCount, statisticCount]`, in that row-major
order. `players` and `stats` identify exact axes; values are signed little-endian
int32. Default public samples contain only eligible current-roster players, never
players whose distributions were withheld. A listed player with no event in a
specific complete game has an explicit zero; missing IDs never imply zero.

The uncompressed bound is 8,000,000 bytes and the compressed bound is 2,000,000
bytes. Shapes, byte counts and complete-game counts must reconcile. If a research
configuration exceeds this budget, player parameter samples are unavailable;
they are never truncated into an apparently valid result. The server-side
TypeScript decoder in `lib/player-props/bootstrap.ts` validates the binary data
and can evaluate a newly requested exact threshold without another 10,000-game
run. Python and TypeScript intervals were compared on an actual current-season
10,000-game run and matched.

## Selected correlated combinations

`inputContext.selectedOutcomes` maps two to twelve contract IDs to `yes` or `no`.
The existing `contractDefinitions` list remains bounded to 32 definitions.
`result.combination` evaluates those selections on shared simulated plays, reports
the independence-product comparison separately, and retains numeric pushes.
Parameter-bootstrap joint sensitivity uses the same selected outcomes. A marginal
histogram alone cannot establish joint probability; the saved joint table or a
new complete-game run of the selected definitions is required. This does not
establish that event contracts are offered as a combinable sportsbook parlay.

## What-if availability

`inputContext.whatIf` accepts only `{playerId,status}`, with active, limited or
inactive status. An exact current-roster identity and sufficient explicitly
labeled historical cohorts are required. Unsupported cohorts or combined injury
assumptions fail without arbitrary multipliers. Hypothetical results are marked
in `result.hypothetical` and `research.whatIf`; current injury reports are never
changed. Snap, weather, pace and efficiency adjustments are not silently applied.

The new `research.playerCatalog` contains verified current-roster IDs, actual
source names/aliases, teams and positions for provider identity resolution. It is
not limited to players who happened to appear in the simulated opportunity pool.

## Verification

Synthetic tests exercise exact thresholds, equality/refund semantics, YES/NO
correlation, scorer-TD scope, sample bounds, decoded dimensions, missing-player
handling and independent parameter sampling. They are not NFL accuracy evidence.
The separate actual-source record in `docs/reports/v6-automatic-python-props.json`
uses 10,000 complete games plus 1,000 parameter games. Its predeclared example
thresholds are explicitly hypothetical research values, not invented DraftKings
contracts or prices. Historical player-prop validation is reported separately;
no live calibration artifact or model promotion is fabricated.
