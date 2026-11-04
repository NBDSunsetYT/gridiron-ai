"""Aggregate frozen forecasts; never tunes/refits the model or edits a run."""
from pathlib import Path
from collections import defaultdict
from datetime import datetime,timezone
import json,math,hashlib,gzip,statistics
import numpy as np
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'artifacts/engine-v15';REPORT=ROOT/'docs/reports';rng=np.random.default_rng(15030)
paths=list((BASE/'runs').glob('*.summary.json'))+list((BASE/'candidate-hurdle/runs').glob('*.summary.json'))+list((BASE/'nba/runs').glob('*.summary.json'))+list((BASE/'nba/runs-15.1.1').glob('*.summary.json'))
groups=defaultdict(list);errors=[];seen=set();inventory=[];runPaths={}
for path in sorted(paths):
 r=json.loads(path.read_text())
 if r.get('status')!='evaluated':errors.append({'gameId':r['gameId'],'reason':r.get('error')});continue
 if not r.get('modelVersion'):
  artifact=path.with_name(path.name.replace('.summary.json','.gz'));r['modelVersion']=json.loads(gzip.decompress(artifact.read_bytes()))['result']['modelVersion']
 key=(r['gameId'],r['modelVersion']);assert key not in seen;seen.add(key);runPaths[key]=path;groups[(r['sport'],r['modelVersion'],r['phase'])].append(r);inventory.append({'gameId':r['gameId'],'sport':r['sport'],'phase':r['phase'],'modelVersion':r['modelVersion'],'eventStart':r['eventStart'],'fitCutoff':r['fitCutoff'],'simulations':r['simulations'],'summarySha256':hashlib.sha256(path.read_bytes()).hexdigest()})
def mean(x):return float(np.mean(x)) if len(x) else None
def scoremetrics(errors):
 a=np.array(errors,float);return {'scoreMAE':mean(abs(a)),'scoreRMSE':float(np.sqrt(np.mean(a*a))),'bias':mean(a),'medianAbsoluteError':float(np.median(abs(a)))}
def bootstrap(rows):
 # Resample calendar weeks, preserving games/teams within each sampled week.
 weeks=defaultdict(list)
 for r in rows:
  d=datetime.fromisoformat(r['eventStart'].replace('Z','+00:00'));weeks[d.strftime('%G-%V')].append(r)
 blocks=list(weeks.values());estimates=[];deltas=[]
 for _ in range(2000):
  sample=[r for i in rng.integers(0,len(blocks),len(blocks)) for r in blocks[int(i)]];a=np.array([e for r in sample for e in r['scoreErrors']]);b=np.array([e for r in sample for e in r['baselineScoreErrors']]);estimates.append(float(abs(a).mean()));deltas.append(float(abs(a).mean()-abs(b).mean()))
 return {'method':'2000 seeded calendar-week block bootstrap replicates','weeks':len(blocks),'scoreMAEInterval95':np.quantile(estimates,[.025,.975]).tolist(),'modelMinusBaselineMAEInterval95':np.quantile(deltas,[.025,.975]).tolist()}
output=[]
for (sport,version,phase),rows in sorted(groups.items()):
 e=[v for r in rows for v in r['scoreErrors']];be=[v for r in rows for v in r['baselineScoreErrors']];cal=[]
 for lower in np.arange(0,1,.1):
  bucket=[r for r in rows if min(9,int(r['homeProbability']*10))==int(round(float(lower)*10))]
  if bucket:cal.append({'lower':round(float(lower),1),'n':len(bucket),'predicted':mean([r['homeProbability'] for r in bucket]),'observed':mean([r['actualHomeWin'] for r in bucket])})
 assert sum(b['n'] for b in cal)==len(rows), 'Calibration buckets must include each game exactly once'
 props=defaultdict(list)
 for r in rows:
  for p in r.get('playerErrors',[]):
   if p['mean']==0 and p['actual']==0:continue
   props[p['stat']].append(p)
 pm={}
 coverage=[]
 for r in rows:
  source=runPaths[(r['gameId'],r['modelVersion'])]
  archived=json.loads(gzip.decompress(source.with_name(source.name.replace('.summary.json','.gz')).read_bytes()))['result'];coverage.append({'forecastPlayers':len(archived.get('players',{})),'matchedPlayers':len({p['id'] for p in r.get('playerErrors',[])})})
 for stat,ps in sorted(props.items()):
  a=np.array([p['error'] for p in ps]);paired=[p for p in ps if p.get('baseline') is not None]
  pm[stat]={'observations':len(ps),'mae':mean(abs(a)),'rmse':float(np.sqrt(np.mean(a*a))),'bias':mean(a),'medianAbsoluteError':float(np.median(abs(a))),'coverage90':mean([p['covered90'] for p in ps]),'pairedBaselineObservations':len(paired),'pairedModelMAE':mean([abs(p['error']) for p in paired]),'pairedBaselineMAE':mean([abs(p['baseline']-p['actual']) for p in paired])}
 result={'sport':sport,'modelVersion':version,'phase':phase,'games':len(rows),'simulatedCompleteGames':sum(r['simulations'] for r in rows),**scoremetrics(e),'baselineScoreMAE':mean(np.abs(be)),'brier':mean([r['brier'] for r in rows]),'logLoss':mean([r['logLoss'] for r in rows]),'totalMAE':mean([abs(sum(r['scoreErrors'])) for r in rows]),'marginMAE':mean([abs(r['scoreErrors'][0]-r['scoreErrors'][1]) for r in rows]),'calibration':cal,'playerStatistics':pm,'bootstrap':bootstrap(rows),'playerCoverage':{'forecastPlayers':sum(c['forecastPlayers'] for c in coverage),'playersWithAtLeastOneVerifiedStat':sum(c['matchedPlayers'] for c in coverage),'warning':'Only exact stable-ID matched statistics are scored. Unverified absences and unmatched players are not silently assigned zero. Missing starters reduce coverage and can bias conditional error metrics.'},'strictPregameQualifiedGames':0,'promoted':False,'promotionReason':'Not promoted: original publication/lineup/injury coverage is unverified. No validated full-game accuracy improvement or approved calibration artifact is claimed.','cpuSeconds':sum(r['cpuSeconds'] for r in rows)}
 output.append(result)
expected=500+40;unique={r['gameId'] for r in inventory};report={'schemaVersion':1,'status':'historical_audit_complete' if len(unique)>=expected else 'historical_audit_running','generatedAt':datetime.now(timezone.utc).isoformat(),'message':'Real complete-game simulations audited against published final results. These are experimental, uncalibrated retrospective models. Original pregame publication, injury and lineup archives are incomplete; no validated model promotion or market advantage is claimed.','uniqueEvaluatedGames':len(unique),'footballUniqueEvaluatedGames':len({r['gameId'] for r in inventory if r['sport']!='NBA'}),'nbaUniqueEvaluatedGames':len({r['gameId'] for r in inventory if r['sport']=='NBA'}),'strictPregameQualifiedGames':0,'forecastRuns':len(inventory),'simulatedCompleteGames':sum(r['simulations'] for r in inventory),'promoted':False,'groups':output,'failures':errors,'protocol':{'selectionSeeds':{'football':15015,'NBA':15016},'defaultGamesPerForecast':10000,'footballTestTrainingCutoff':'2025-11-15T00:00:00+00:00','nbaTestTrainingCutoff':'2025-04-01T00:00:00+00:00','testRefitting':'None. All parameters and roster features frozen before the final period.','evaluationOnlyFinals':'Forecast compressed artifact is written before final-stat retrieval. Actuals never enter that forecast.','baseline':'Prior recent team scoring/conceding averages; player prior-game means on matched observations. No historical lines fabricated.'},'limitations':['Football development250 uses candidate15.0.0; later validation/test use candidate15.1.0. They must not be pooled as one model’s accuracy.','NBA15.0.0 initial development and15.1.1 revised development are reported separately. Repeated games do not increase the unique sample count.','All models are unpromoted candidates. Missing original availability timestamps, historical injury/lineup archives and source corrections prevent a strict prospective validation claim.','Frozen final-test rosters may become stale across weeks. This is intentionally conservative and not a claim of injury-adjusted live performance.','No verified historical contract thresholds/fees/settlement rules were available. Prop over/under win rates and market superiority are not graded.','Football special-teams scores, live-ball penalties, exact period-specific overtime and causal personnel/weather effects remain incomplete. NBA technical/bonus administration, team rebounds, causal rest/blowout and injury effects remain incomplete.','Monte Carlo Wilson intervals quantify sampling variation, not total model uncertainty. No raw hit rate is labeled calibrated.'],'inventory':inventory}
REPORT.mkdir(exist_ok=True);(REPORT/'v15-validation.json').write_text(json.dumps(report,indent=2)+'\n')
for g in output:print(json.dumps({k:g[k] for k in ['sport','modelVersion','phase','games','scoreMAE','baselineScoreMAE','bias','brier']}))
print(json.dumps({'uniqueGames':len(unique),'forecastRuns':len(inventory),'simulatedCompleteGames':report['simulatedCompleteGames'],'failures':len(errors),'status':report['status']}))
# Standalone exportable calibration figure; same underlying raw probability bins.
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
fig,ax=plt.subplots(1,3,figsize=(14,4),constrained_layout=True)
for axis,sport in zip(ax,['NFL','CFB','NBA']):
 axis.plot([0,1],[0,1],'--',color='#888888',label='Ideal reliability')
 for g in output:
  if g['sport']==sport and g['phase'] in ['validation','test']:
   axis.plot([b['predicted'] for b in g['calibration']],[b['observed'] for b in g['calibration']],marker='o',label=f"{g['phase']} n={g['games']}")
 axis.set(xlim=(0,1),ylim=(0,1),xlabel='Raw home-win probability',ylabel='Observed home-win frequency',title=sport+' retrospective candidate');axis.legend(fontsize=8)
fig.savefig(REPORT/'v15-calibration.png',dpi=180)
