"""Freeze metadata-only chronological selections before V20 experiments."""
import sys,json,gzip,random,hashlib
from pathlib import Path
from collections import defaultdict
from datetime import datetime,timedelta,timezone
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from modeling.structural_v18.data import archives
from modeling.iterative_learning import freeze_json
OUT=ROOT/'artifacts/overnight-v20';OUT.mkdir(parents=True,exist_ok=True)
if (OUT/'protocol.json').exists():print('Protocol already frozen');sys.exit(0)
excluded={'cfb:espn:401858509','cfb:espn:401756926','2025_07_LA_JAX','2025_13_KC_DAL'}
for p,key in [('artifacts/engine-v15/selection.json','selection'),('artifacts/engine-v15/nba/selection.json','games'),('artifacts/learning-v16/protocol.json','selection')]:excluded.update(g['id'] for g in json.load((ROOT/p).open())[key])
for name in ['structural-v18','parallel-v19']:
 p=json.load((ROOT/'artifacts'/name/'protocol.json').open())
 for gs in p['selection'].values():excluded.update(g['id'] for g in gs)
windows={'NFL':[['2024-10-01','2024-11-01'],['2024-11-01','2024-12-01'],['2025-09-01','2025-10-01'],['2025-11-01','2025-12-01']], 'CFB':[['2024-10-01','2024-11-01'],['2024-11-01','2024-12-01'],['2025-09-01','2025-10-01'],['2025-11-01','2025-12-01']], 'NBA':[['2024-12-01','2025-01-01'],['2025-02-01','2025-03-01'],['2025-12-01','2026-01-01'],['2026-02-01','2026-03-01']]};rng=random.Random(20020);selection={};counts={};sealed={}
for sport in ['NFL','CFB','NBA']:
 data=archives(sport);meta=[]
 if sport=='NBA':
  for g in data.values():
   if len(g['teams'])!=2:continue
   sides={t['team_home_away']:str(tid) for tid,t in g['teams'].items()}
   if set(sides)!={'home','away'}:continue
   meta.append({'id':g['id'],'sport':sport,'at':g['at'],'end':g['at'],'home':sides['home'],'away':sides['away'],'season':g['season']})
 else:
  for g in data['games'].values():
   if g['plays']>=70:meta.append({k:g[k] for k in ['id','sport','home','away','season']}|{'at':g['firstObservedAt'],'end':g['lastObservedAt']})
 history=defaultdict(list)
 for g in meta:
  for t in [g['home'],g['away']]:history[t].append(g['end'])
 qualified=[g for g in meta if all(sum(t<g['at'] for t in history[team])>=5 for team in [g['home'],g['away']])]
 rows=[];counts[sport]=[]
 for c,(start,end) in enumerate(windows[sport]):
  eligible=[g for g in qualified if start<=g['at'][:10]<end and g['id'] not in excluded];rng.shuffle(eligible);n=min(75,len(eligible));counts[sport].append({'cohort':c,'eligible':len(eligible),'selected':n});rows.extend(g|{'cohort':c,'fullGame':i<12} for i,g in enumerate(eligible[:n]))
 selection[sport]=sorted(rows,key=lambda g:(g['cohort'],g['at'],g['id']))
 boundary='2026-03-15' if sport=='NBA' else '2025-12-15';eligible=[g for g in qualified if g['at'][:10]>=boundary and g['id'] not in excluded and g['id'] not in {r['id'] for r in rows}];rng.shuffle(eligible);sealed[sport]=[{'id':g['id'],'sport':sport,'at':g['at']} for g in eligible[:30]]
sourceFiles=json.load((ROOT/'artifacts/parallel-v19/protocol.json').open())['sourceFiles'];protocol={'id':'overnight-v20.0.0','seed':20020,'selection':selection,'counts':counts,'excludedEvaluationIds':sorted(excluded),'sealedFinal':sealed,'sealedFinalOpened':False,'v19ProspectiveFinal':'2026-11-05 onward remains separate and unopened','sourceFiles':sourceFiles,'windows':windows,'maximumActiveSeconds':36000,'maximumCpuSeconds':36000,'maxParallelProcesses':2,'maximumCampaignBytes':550000000,'minimumFreeBytes':268435456,'workerMaxRssBytes':3221225472,'trials':10000,'preliminaryTrials':1000,'fullGamePerWindow':12,'primaryMetrics':{'footballPlayer':'passingYards MAE on a predefined past-role roster','nbaPlayer':'rebounds MAE on a predefined past-role roster','game':'moneyline Brier with team-score MAE guardrail'},'criticalGuardrails':{'minimumIndependentGamesForQualifiedReview':200,'minimumWindows':3,'minimumPointInTimeAvailabilityCoverage':.9,'maximumImportantCategoryRelativeRegression':.03,'maximumBrierRegression':0,'maximumLogLossRegression':0,'paired95IntervalUpperMustBeNegative':True},'maximumConsecutiveNonImprovingCandidates':20,'productionPromotionsAllowed':False,'dataQualityPolicy':'No inferred publication dates. Unknown historical source publication stays null; corrected-history sensitivity experiments are separate from strictly point-in-time qualified forecasts.','hypotheses':['NFL/CFB known pregame out designations and learned quarterback continuity may repair participant mismatch without using final lineups.','NFL/CFB separately learned team pass/play opportunity budgets may improve full-game volume beyond state-only fitting.','NBA rebound share per observed missed-shot opportunity can outperform per-minute rebound weights.','NBA rebounds cannot be credited after a modeled period-ending shot at the buzzer.','Chronological opportunity/efficiency point models should be compared against rolling means before full-game promotion.']}
freeze_json(OUT/'protocol.json',protocol);freeze_json(ROOT/'docs/reports/overnight-v20-protocol.json',protocol);print(json.dumps({'selected':{s:len(v) for s,v in selection.items()},'fullGames':{s:sum(g['fullGame'] for g in v) for s,v in selection.items()},'counts':counts,'sealed':{s:len(v) for s,v in sealed.items()}}))
