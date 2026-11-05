"""Render measured, frozen V20 results. No training, simulations or network IO."""
import json,csv,re,subprocess,sys,hashlib
from pathlib import Path
from datetime import datetime,timezone
from zoneinfo import ZoneInfo
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from modeling.overnight_v20.state import read,atomic
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
R=ROOT/'docs/reports';OUT=ROOT/'artifacts/overnight-v20';r=read(R/'accuracy-first-v20.json');state=read(OUT/'runtime/state.json');confirm=r['forwardConfirmation'];rows=[]
for sport,l in r['leagues'].items():
 for phase,cats in l['phaseBenchmarks'].items():
  for stat,families in cats.items():
   for name,c in families.items():
    if not c['metrics']:continue
    d=c['primaryMAEDelta'];rows.append(dict(sport=sport,phase=phase,stat=stat,model=name,games=c['games'],observations=c['observations'],mae=c['metrics']['mae'],rmse=c['metrics']['rmse'],bias=c['metrics']['bias'],baselineMAE=c['baseline']['mae'],pairedDelta=d['mean'],ciLow=d['bootstrap95'][0],ciHigh=d['bootstrap95'][1]))
for sport,l in confirm['leagues'].items():
 for stat,families in l.get('categories',{}).items():
  for name,c in families.items():
   if not c['metrics']:continue
   d=c['primaryMAEDelta'];rows.append(dict(sport=sport,phase='fresh_confirmation',stat=stat,model=name,games=c['games'],observations=c['observations'],mae=c['metrics']['mae'],rmse=c['metrics']['rmse'],bias=c['metrics']['bias'],baselineMAE=c['baseline']['mae'],pairedDelta=d['mean'],ciLow=d['bootstrap95'][0],ciHigh=d['bootstrap95'][1]))
with (R/'overnight-v20-benchmarks.csv').open('w') as f:
 w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
plt.rcParams.update({'figure.facecolor':'#101419','axes.facecolor':'#101419','axes.edgecolor':'#83909d','text.color':'#f1f4f7','axes.labelcolor':'#f1f4f7','xtick.color':'#c9d2dc','ytick.color':'#c9d2dc','font.size':9,'savefig.facecolor':'#101419'})
fig,axes=plt.subplots(1,3,figsize=(12,4.5),layout='constrained')
for sport,ax in zip(['NFL','CFB','NBA'],axes):
 primary='rebounds' if sport=='NBA' else 'passingYards';c=r['leagues'][sport]['phaseBenchmarks']['validation'][primary]['opportunity_hurdle'];points=[('Earlier validation',c)]
 if confirm['leagues'][sport].get('primary'):points.append(('Fresh confirmation',confirm['leagues'][sport]['primary']))
 for i,(label,c) in enumerate(points):
  d=c['primaryMAEDelta'];lo,hi=d['bootstrap95'];ax.errorbar(d['mean'],i,xerr=[[max(0,d['mean']-lo)],[max(0,hi-d['mean'])]],fmt='o',color='#47e5ca' if i==0 else '#e5b860',capsize=5);ax.text(.02,.94-i*.1,f"{label}: {c['games']} games / {c['observations']} pairs",transform=ax.transAxes,fontsize=8)
 ax.axvline(0,color='#db6e75',linestyle='--',alpha=.8);ax.set_yticks(range(len(points)),[p[0] for p in points]);ax.set_ylim(-.6,1.7);ax.set_title(sport+' · '+primary);ax.set_xlabel('Hurdle MAE − rolling MAE (original stat units)');ax.grid(axis='x',alpha=.12)
fig.suptitle('V20 opportunity/efficiency head · game-clustered paired 95% intervals\nNegative favors the candidate. Corrected-history research; no production qualification.',fontsize=11)
fig.savefig(R/'overnight-v20-paired-errors.png',dpi=150);plt.close(fig)
fig,axes=plt.subplots(1,3,figsize=(11,4),layout='constrained')
for sport,ax in zip(['NFL','CFB','NBA'],axes):
 for name,m in r['leagues'][sport]['probabilityAndIntervals'].items():
  raw=m['rawMoneyline'];xs=[b['meanPredicted'] for b in raw['bins']];ys=[b['observed'] for b in raw['bins']];ax.plot(xs,ys,'o-',label=name.replace('_',' '),alpha=.8)
 ax.plot([0,1],[0,1],'--',color='#83909d');ax.set(xlim=(0,1),ylim=(0,1),xlabel='Raw home-win probability',ylabel='Observed frequency',title=f"{sport}: {m['games']} matched games");ax.legend(fontsize=7);ax.grid(alpha=.1)
fig.suptitle('Raw moneyline reliability · small samples, no fitted calibration applied',fontsize=12);fig.savefig(R/'overnight-v20-reliability.png',dpi=150);plt.close(fig)

def fmt(x,d=3):return f'{x:.{d}f}' if isinstance(x,(float,int)) else 'Unavailable'
def table(headers,body):return '\n'.join(['| '+' | '.join(headers)+' |','| '+' | '.join(['---']*len(headers))+' |',*['| '+' | '.join(str(x) for x in row)+' |' for row in body]])
def ci(d):return f"{d['mean']:.3f} [{d['bootstrap95'][0]:.3f}, {d['bootstrap95'][1]:.3f}]"
now=datetime.now(timezone.utc);hours=lambda s:f'{s/3600:.3f} h ({s:.1f} s)';tests=read(OUT/'verification.json',{'status':'not_finalized'});observed=state['measuredActiveSeconds'];safety=state.get('setupSafetyChargeSeconds',0)+state.get('unobservedActiveUpperBoundSeconds',0);measured_cpu=sum(j.get('receipt',{}).get('cpuSeconds',0) for j in state['jobs'].values());basegames=sum(l['evaluatedProjectionGames'] for l in r['leagues'].values());newgames=sum(l['gradedGames'] for l in confirm['leagues'].values());obs=sum(l['playerObservations'] for l in r['leagues'].values())+sum(l.get('observations',0) for l in confirm['leagues'].values());local=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
text=f'''# GRIDIRON AI V20 — accuracy-first research checkpoint

Recorded {now.astimezone(ZoneInfo('America/New_York')).strftime('%B %d, %Y, %I:%M %p Eastern')} ({now.isoformat()}).

Production is unchanged. No model was promoted, no production database was queried or modified, and no paid resources or billing settings were changed. This is an implemented and executed research phase on `research/overnight-v20`, continuing V19.

The central result is conditional progress, not validated overall superiority. The opportunity/efficiency head reduced some historical mean errors. The preregistered fresh NBA confirmation did **not** establish a statistically reliable improvement. Critical point-in-time and joint-distribution gates remain unsatisfied.

## Execution, scope and stop condition

- {basegames+newgames} distinct games received graded player projections: {basegames} in the initial study and {newgames} in one separately locked forward confirmation. Twelve additional NFL events were audited but withheld for insufficient pregame participant history. {obs:,} game/player/stat observations were graded; these are not independent games.
- Four complete-game cohort iterations, twelve point-benchmark cohort iterations, and two league-specific forward confirmation batches completed. Six point challengers per league (18 league/configuration combinations), two full-game alternatives per league (6 combinations), plus explicit baselines were examined. Windows/stat heads/seed repeats are not new architectures. One preliminary hurdle process was interrupted and retained, not counted as a completed experiment.
- 1,290,000 accepted complete-game realizations, 30,000 completed but quarantined realizations, and 21,000 diagnostic/replay realizations: **1,341,000 total**. These preceded the accuracy-first simulation pause. The point suite and forward confirmation added **zero** game simulations. No 50,000/100,000-trial batch was run merely to improve apparent precision.
- Observed campaign active time at this checkpoint: **{hours(observed)}**. Separate conservative setup/unknown-gap budget charge: **{hours(safety)}**. Sum charged toward the 10-hour ceiling: **{hours(observed+safety)}**. Unknown gaps are not reported as active computation.
- Measured CPU in completed simulation/benchmark/diagnostic/confirmation job receipts: **{measured_cpu:.3f} seconds**. Separately reserved, not measured: 600 seconds of preflight CPU and 600 seconds for the interrupted preliminary hurdle. Source reconstruction, audits, browser tests and builds have additional CPU outside those job receipts; a complete process-tree CPU total is unavailable.
- A detached controller was actually launched and survived multiple tool calls. The environment offers no verified ten-hour survival guarantee after VM shutdown. There is no claim of inactive/background execution. The heavy queue is paused and the checkpoint is resumable.
- Stop condition: **insufficient original pregame evidence and unresolved coarsened CFB clock semantics for safe further full-game tuning**. The locked lower-cost benchmark/confirmation objectives completed. Neither the ten-hour limit nor twenty consecutive novel failed candidates was reached.

## Point-in-time evidence and selective forecasting

Every selected game and earlier-known player has a versioned evidence record covering identity, historical statistics, injuries, lineup, participation, and football weather. Original publication or a genuine immutable pre-cutoff capture is required. A provider's modification time is not silently treated as original publication. The score is source coverage, not model confidence. Unknown injury evidence never means healthy.

'''
text+=table(['League','Audited / graded initial games','Player-game evidence pairs','Verified availability pairs','Complete original pregame games'],[[s,f"{l['evidenceCoverage']['games']} / {l['evaluatedProjectionGames']}",l['evidenceCoverage']['players'],l['evidenceCoverage']['playersWithVerifiedAvailabilityFact'],l['evidenceCoverage']['completePointInTimeGames']] for s,l in r['leagues'].items()])
text+='''

NFL: 1,418 provider-timestamped injury facts were preserved but cannot certify original publication; none passes the strict original-publication availability gate. CFB: sparse official conference PDFs resolve only 18 selected player-game availability records. NBA: corrected historical PDF URL formats and column parsing resolve 292 player-game availability records in the initial study. The fresh NBA batch adds 186 source facts covering 21 games, with 106 mapped player-game availability facts. Its NFL dates have zero accessible historical report facts. No league has complete original lineup/participation/statistical-publication coverage.

Eight exact NBA trade-related ownership ambiguities were resolved from official dated transaction articles before cutoff. Thirty wrong-team zero-result grade rows were withdrawn in the **new** audit; original forecasts/grades remain intact. Ownership does not establish health, a starting role or expected minutes. Publisher metadata is not an independently captured pregame archive.

The research policy withholds unconditional forecasts when critical evidence or quantified model uncertainty is missing. Corrected-history conditional projections remain available for diagnostics. This policy is research-local and does not rewrite production predictions.

## Structural implementations and confirmed defects

1. Separate NFL/CFB/NBA opportunity-and-efficiency heads model participation/nonzero opportunity, conditional opportunity volume, and conditional yield. Fixed regularization and earlier-only fitting replace an undifferentiated statistic regression. NFL and CFB coefficients are fitted separately. These point heads do not pretend to be complete-game samples.
2. Full football candidates introduce a fitted team-volume bridge and current-season quarterback-continuity scenarios. A known-out last quarterback previously caused preflight failure before backup plans were considered. A new research-only conditional personnel planner preserves verified flags and generates only historically supported, unweighted backup scenarios. The Dallas–Philadelphia preflight now resolves one conditional scenario without reading its final box or running a new simulation. Unsupported active probabilities are not invented.
3. CFB raw training data contains 4,465 zero-elapsed positive rushes among 19,094 such rushes (23.38%). One learned conditional rush timing distribution puts 77.74% probability on zero duration. The historical official ESPN payload also repeats `15:00` across distinct rush, reception and incompletion plays. Treating these coarsened zeros as independent physical runoff can inflate plays. One event produced means 141.364 / 45.508 and 337.591 plays; its three 10,000-game outputs were quarantined. True per-snap times cannot be recovered from that source by guessing. No validated numerical clock repair is claimed.
4. NBA rebound candidates partially pool offensive/defensive rebound shares against team opportunities, exclude rebound credit for period-ending misses, and use the correct modeled period possession pattern. Team/player counts reconcile, but empirical accuracy gains are not assumed from rule fixes.
5. Five missing NBA final-box grades now use a versioned category-level reconciler. Unmapped nonzero outcomes, unknown minutes and unbalanced point totals are withheld independently; supported categories are retained. A surname-only `Olbrich` row with missing athlete identity/minutes was not guessed into a player record. Eighty-four fresh NBA forecast/stat rows remain ungraded rather than receiving fabricated values.
6. Game-level paired bootstraps preserve clustering; observation-weighted MAE deltas and their intervals use the same estimand. A separate conservative 18-comparison sensitivity analysis prevents selecting the best-looking family without qualification.
7. Runtime accounting distinguishes live processes from zombies, measured time from suspension gaps, and distinct candidates from repeated windows. Local-only checks reject unpromoted research in Vercel/Render environments. No simulations were moved into hosted request handlers.

## Benchmark suite and expected-value results

Families: rolling five-game means; opponent-adjusted rolling residuals; ridge regression; regularized player/team partial pooling; histogram gradient boosting; a regularized hybrid; and the new opportunity hurdle. The partial-pooling model is empirical regularization, not a claimed full Bayesian posterior. The matched joint simulator is reported separately on its smaller supported actor/event frame. All categories, counts, bias, RMSE and intervals are in [the CSV](overnight-v20-benchmarks.csv) and [machine-readable report](accuracy-first-v20.json).

Later chronological validation only; development window zero is excluded below. Negative paired MAE differences favor the candidate. Units are yards for football and rebounds for NBA.

'''
body=[]
for s,l in r['leagues'].items():
 p='rebounds' if s=='NBA' else 'passingYards';c=l['phaseBenchmarks']['validation'][p]['opportunity_hurdle'];body.append([s,p,f"{c['games']} / {c['observations']}",fmt(c['baseline']['mae']),fmt(c['metrics']['mae']),fmt(c['baseline']['rmse']),fmt(c['metrics']['rmse']),ci(c['primaryMAEDelta'])])
text+=table(['League','Primary','Games / pairs','Rolling MAE','Hurdle MAE','Rolling RMSE','Hurdle RMSE','Paired MAE delta [95%]'],body)
text+='''

CFB's pooled unadjusted interval is favorable, but window one regresses and its 18-comparison sensitivity includes no improvement. NBA's earlier mean-error signal survives that sensitivity check, but its fresh confirmation does not establish improvement. NFL's initial interval includes no improvement. No overall production qualification follows from any of these point-mean results.

![Paired expected-value errors](overnight-v20-paired-errors.png)

## Locked forward confirmation — no retuning

Selected from metadata only after earlier results, excluding all earlier examined IDs and the 79 sealed final games. Fixed model families/hyperparameters were frozen before grading. A single fit uses only earlier data. This is fresh conditional historical confirmation, not a fully verified prospective test. No CFB games remained in the eligible forward interval before the sealed boundary, so none was substituted from the final set.

'''
text+=table(['League','Games / primary pairs','Rolling MAE','Hurdle MAE','Paired delta [95%]','Conclusion'],[[s,f"{l['gradedGames']} / {l['primary']['observations']}",fmt(l['primary']['baseline']['mae']),fmt(l['primary']['metrics']['mae']),ci(l['primary']['primaryMAEDelta']),'Not established; interval includes zero'] for s,l in confirm['leagues'].items() if 'primary' in l])
text+='''

NBA has 75 fresh games and 2,142 rebound observations. NFL has seven fresh games and 29 passing-yard observations. Replacing the locked primary with a better-looking secondary after seeing these outcomes would be selection bias; it was not done. No further tuning uses this confirmation set.

## Joint-game probability and interval evaluation

Accepted complete-game event counts are 23 NFL, 11 CFB and nine NBA, with three modeled variants each. These samples are far below the predeclared independent-game qualification gate. Scores, player means, Brier/log loss, CRPS and 50/80/90/95% prediction interval coverage are evaluated independently. Raw Monte Carlo hit rates are never labeled calibrated; no newly fitted calibration model or market-probability copy is used.

'''
text+=table(['League','Variant','Games','Team-score MAE','Raw Brier','Raw log loss','Raw ECE'],[[s,name,m['games'],fmt(m['teamScore']['mae']),fmt(m['rawMoneyline']['brier'],5),fmt(m['rawMoneyline']['logLoss'],5),fmt(m['rawMoneyline']['ece'],5)] for s,l in r['leagues'].items() for name,m in l['probabilityAndIntervals'].items()])
text+='\n\n'+table(['League','Variant','Paired games','Brier delta [95%]','Score MAE delta [95%]'],[[s,name,m['pairedGames'],ci(m['brierDelta']),ci(m['scoreMAEDelta'])] for s,l in r['leagues'].items() for name,m in l['jointGameComparisons'].items()])
text+='''

CFB's quarterback mixture lowers Brier while worsening score MAE; NBA's joint candidate slightly worsens Brier/log loss. NFL directionally improves, but the paired uncertainty includes no improvement. Better mean projections alone do not validate moneylines or tails. NBA rebound point-head gains have not been proven in an independently validated joint simulation.

![Raw reliability diagnostics](overnight-v20-reliability.png)

## Error attribution and systematic-error ranking

The implementation uses exact product/Shapley decompositions of opportunity × efficiency, and an NBA minutes-fraction × team rebound-opportunity × rebound-share decomposition. Signed and absolute-error contributions reconcile numerically. They are descriptive allocations, not causal injury/lineup effects or percentages of preventable error. Negative contributions can offset other errors.

'''
text+=table(['League / category','Supported games / actors','Mean absolute-error contributions'],[[s+' / '+stat,f"{a['games']} / {a['observations']}",'; '.join(k+'='+fmt(v) for k,v in a['meanAbsoluteErrorContributions'].items())] for s,l in r['leagues'].items() for stat,a in l['attribution'].items() if a['observations']])
text+='''

Separate snap time and football pace effects are not identifiable from these aggregate archives. NBA on-court missed shots are proxied by minutes; this cannot establish lineup causality. A distribution-assumption contribution to one realized mean error is unidentifiable and remains null. Distribution quality is assessed separately with proper scores and interval coverage. Player projections without supported opportunity distributions are excluded from that decomposition and retain their ordinary forecast error.

The dashboard ranks recurring bias by prior role/opportunity group, rather than presenting one extreme game as the only cause. Complete ranked groups, season results, window-specific changes and promotion rejection reasons are in the JSON report.

## Temporal integrity, markets and storage

- Four chronological cohort windows per league; window zero development and windows one–three validation. Training uses at most 500 earlier completed games with a six-hour embargo. Earlier event history can update features; this is rolling walk-forward validation, not a whole-season frozen external test.
- Existing owned archives contain outcomes, but current-game labels are not passed to feature construction or model fitting. Forecast files and model parameters are frozen before the grading stage accesses final boxes. The corrected-history/original-publication limitation remains explicit.
- Previously examined V17 metadata had 72 distinct eligible IDs despite the earlier 342 repeated evaluation rows. Their overlap with V20 selection is zero. Prior V19 evaluation IDs are excluded. The 79 reserved historical final games have zero grading/selection overlap and remain ungraded.
- A broad transaction search incidentally exposed a current Detroit–Philadelphia news result. A timestamped exclusion notice is preserved; it did not intersect V20's historical final set. The potentially affected V19 prospective window must not be represented as wholly untouched. No score was copied into V20 features.
- PropLine's documented Hobby history lookback is 30 days. These historical samples fall outside the useful range. No authenticated historical price response, exact threshold, executable quote, source timestamp or settlement rule was verified in this campaign. Unverified schedule reference lines are excluded. No betting-return/prop calibration or market ensemble is claimed, and sportsbook prices are never called DraftKings Predictions contracts. Existing integrations are preserved.
- Compact simulation records retain model/input/source versions, seed, configuration, histograms, sufficient probability summaries and a few representative games. Every simulated play is not permanently stored. Research-only immutable SQLite snapshots/outbox and backup were restart-tested; verified updates append invalidations and deduplicated bounded refresh work instead of rewriting snapshots. The new watcher/resimulation mechanism is not enabled against production; no live update-to-resimulation success is claimed.
- Supabase, MongoDB, Cloudflare, wallet/P&L and AI histories were left untouched. This phase does not claim a new cross-device production persistence test.

## Dashboard, source changes and verification

The new `/research/v20` page is statically rendered on the research branch with league filters, evidence coverage, ranked repeated misses, seven-family comparisons, raw reliability diagrams, interval coverage, attribution and separate forward confirmation. Its JSON endpoint serves cached report data. Opening the page and switching views cause no API preparation, training or simulation requests. Local production-mode Chromium tests cover desktop and iPhone-sized layouts; no physical iPhone/Safari installation or production deployment was performed.

Important source groups:

- `modeling/accuracy_v20/`: evidence policy, separate opportunity/efficiency models, exact attribution, opponent-adjusted baseline, ownership resolver, selective outcome adapter, conditional personnel, holdout integrity, immutable snapshots/outbox and promotion gates.
- `modeling/overnight_v20/` and `scripts/*v20.py`: bounded resumable research controller, league-specific joint candidates, source reconstruction, cold replay, diagnostics, point-only benchmarks, locked confirmation, cached audit/report generation.
- `components/AccuracyResearchV20.tsx`, `app/research/v20/`, `app/api/engine/route.ts`: read-only research UI and cached report.
- `modeling/test_accuracy_first_v20.py`, `modeling/test_overnight_v20.py`, `tests/accuracy-v20*`: mechanics, temporal isolation, accounting, evidence, snapshots, caching and browser regressions. Synthetic mechanics tests are not historical accuracy evidence.

'''
text+='```json\n'+json.dumps(tests,indent=2)+'\n```\n'
text+=f'''
The production build has an existing health-route JSON named-export warning; it succeeded. The latest GitHub Actions verify job failed with no steps executed. An earlier checkpoint reported an Actions billing/spending guard; the latest annotation endpoint is unavailable through the connected tool. No successful remote CI run is claimed, and no paid setting was changed.

## Recovery, exact resume commands and promotion decision

Branch: `research/overnight-v20`; source checkpoint used to render this report: `{local}`. Public branch checkpoint mappings and verified tree hashes are maintained in `overnight-v20-publication.json` when published. Recovery branch `checkpoint/pre-v20-20261105` and all original forecasts remain available. Source and measured-result archives exclude credentials, raw vendor documents and unnecessary datasets.

From the original checkpoint workspace (source archives and hashes in the frozen protocols must match):

```sh
pip install -r modeling/requirements-overnight.txt
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \\
  python scripts/research-point-only-v20.py
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \\
  python scripts/run-confirmation-v20.py
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \\
  python scripts/audit-accuracy-first-v20.py
python scripts/report-accuracy-v20.py
python scripts/research-overnight-v20.py --status
```

The two completed experiment commands return existing receipts; they do not repeat tuning. The audit returns a cache hit while inputs are unchanged. Full-game `continue-overnight-v20.py --slice-seconds 1800` intentionally refuses to run while `runtime/accuracy-first-pause.json` is set. Do not clear that evidence gate merely to generate more trials. A future numerical/evidence change needs a newly registered revision, fresh eligibility audit and budgets; existing snapshots and the final holdout must remain intact. Reproducing on another machine requires the private checkpoint plus the original source archives identified by SHA-256, not source code alone.

No candidate qualifies for production promotion now. NBA partial pooling/hurdle mean projections merit further research, but the locked fresh primary result is inconclusive and original pregame evidence remains inadequate. CFB needs trustworthy pace/timing and quarterback-participation evidence before safe joint-model tuning. NFL needs original historical availability and a larger independent validation sample. Production, financial records and infrastructure remain preserved.
'''
(R/'overnight-v20-accuracy-first.md').write_text(text)
atomic(OUT/'measured-checkpoint.json',{'recordedAt':now.isoformat(),'runtimeSnapshot':state,'completedJobMeasuredCpuSeconds':measured_cpu,'gradedPlayerProjectionGames':basegames+newgames,'initialGradedProjectionGames':basegames,'freshConfirmationGames':newgames,'playerStatObservations':obs,'completeGameRealizations':1341000,'finalHoldoutGames':79,'finalHoldoutGraded':False,'productionWrites':0,'productionPromotions':0,'stopReason':'insufficient_original_point_in_time_and_clock_evidence','verification':tests,'sourceCheckpointAtReportGeneration':local})
print(json.dumps({'report':str(R/'overnight-v20-accuracy-first.md'),'csvRows':len(rows),'games':basegames+newgames,'observations':obs,'measuredJobCpuSeconds':measured_cpu,'runtimeObservedSeconds':observed}))
