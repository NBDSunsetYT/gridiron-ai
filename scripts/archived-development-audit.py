"""Descriptive multi-season audit; excludes all frozen final-test IDs.
No fitting, promotion, provider calls or new game simulation.
"""
import gzip,hashlib,json,sys,time
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from modeling.calibration_research import metrics
ROOT=Path(__file__).resolve().parents[1]
def load(p):return json.loads(gzip.decompress(p.read_bytes()) if p.suffix=='.gz' else p.read_text())
def error(a):a=np.asarray(a);return {'n':len(a),'mae':float(np.mean(abs(a))),'rmse':float(np.sqrt(np.mean(a*a))),'bias':float(np.mean(a))}
def variance(d):
    bins=d['histogram'];n=sum(b['count'] for b in bins);mean=sum(b['value']*b['count'] for b in bins)/n
    return sum((b['value']-mean)**2*b['count'] for b in bins)/n
start=time.process_time();v15=ROOT/'artifacts/engine-v15';v16=ROOT/'artifacts/learning-v16';manifest=load(v16/'protocol.json');old=load(v15/'selection.json')['selection'];nba=[{**g,'sport':'NBA'} for g in load(v15/'nba/selection.json')['games']];excluded={g['id'] for g in old+nba+manifest['selection'] if g['phase']=='test'};report={'scope':'Retrospective development/validation archives only; no exposed final-test reuse','legacy':{},'pairedCFBDiagnostics':{},'resources':{},'newMonteCarloRuns':0,'productionPromotions':[]}
for sport in ['NFL','CFB','NBA']:
    selection=[g for g in old+nba if g['sport']==sport and g['phase']!='test' and g['id'] not in excluded];rows=[];hashes={}
    for g in selection:
        base=v15/'nba/runs-15.1.1' if sport=='NBA' else v15/'runs';p=base/(g['id'].replace(':','_')+'.json.summary.json')
        if p.exists():
            row=load(p)
            if row['gameId']!=g['id'] or row['phase']=='test':raise RuntimeError('Archive identity mismatch')
            rows.append(row);hashes[str(p.relative_to(ROOT))]=hashlib.sha256(p.read_bytes()).hexdigest()
    groups={}
    for r in rows:
        for p in r['playerErrors']:groups.setdefault(p['stat'],[]).append(p)
    report['legacy'][sport]={'games':len(rows),'calendarYears':sorted({int(r['eventStart'][:4]) for r in rows}),'teamScores':error([e for r in rows for e in r['scoreErrors']]),'moneyline':metrics([r['homeProbability'] for r in rows],[r['actualHomeWin'] for r in rows]),'players':{k:{**error([p['error'] for p in v]),'coverage90':float(np.mean([p['covered90'] for p in v]))} for k,v in groups.items()},'sourceChecksums':hashes,'use':'Descriptive audit only. Different input/model versions are not pooled into a production calibrator.'}
eligible=[g for g in manifest['selection'] if g['sport']=='CFB' and g['phase']=='validation' and g['id'] not in excluded]
for candidate in ['reference-v15','repair-conversions','conditional-clock','stronger-shrinkage']:
    confidence=[];expected=[];margin_vars=[];covariances=[];changes=[];wrong=0
    for game in eligible:
        name=game['id'].replace(':','_');base=v16/'runs'/candidate/'CFB';r=load(base/(name+'.evaluation.json.gz'));f=load(base/(name+'.forecast.json.gz'))['forecast'];p=r['homeProbability'];confidence.append(max(p,1-p));expected.append(p if r['actualHomeWin'] else 1-p);wrong+=int((p>.5)!=bool(r['actualHomeWin']));vm=variance(f['marginDistribution']);vt=variance(f['totalDistribution']);margin_vars.append(vm);covariances.append((vt-vm)/4)
        original=load(v16/'runs/reference-v15/CFB'/(name+'.evaluation.json.gz'));changes.append({'gameId':game['id'],'brierChange':r['brier']-original['brier'],'referenceProbability':original['homeProbability'],'candidateProbability':p,'actualHomeWin':r['actualHomeWin']})
    report['pairedCFBDiagnostics'][candidate]={'games':len(eligible),'meanFavoriteProbability':float(np.mean(confidence)),'meanProbabilityAssignedToActualWinner':float(np.mean(expected)),'incorrectWinnerDirections':wrong,'meanSimulatedMarginVariance':float(np.mean(margin_vars)),'meanSimulatedScoreCovariance':float(np.mean(covariances)),'largestBrierRegressions':sorted(changes,key=lambda r:r['brierChange'],reverse=True)[:5],'causalInterpretation':'Paired descriptive evidence only. Mean-score error and Brier loss measure different objects; no causal attribution from one game.'}
report['resources']={'cpuSeconds':time.process_time()-start,'providerRequests':0,'simulationRuns':0};report['excludedFinalGameCount']=len(excluded)
(ROOT/'docs/reports/development-audit-v17.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
print(json.dumps({'legacyGames':{s:r['games'] for s,r in report['legacy'].items()},'cpuSeconds':report['resources']['cpuSeconds'],'simulations':0}))
