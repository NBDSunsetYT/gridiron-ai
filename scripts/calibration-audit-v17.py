"""Bounded local audit of EXISTING forecasts. No Monte Carlo, HTTP or promotion.

Already exposed final tests are excluded using the frozen selection manifest,
before opening any evaluation file. Outputs are new artifacts; originals stay intact.
"""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import resource
import sys
import time
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from modeling.calibration_research import fit,predict,metrics,paired_interval,chronological_windows

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'artifacts/learning-v16'
def read(path):return json.loads(gzip.decompress(path.read_bytes()))
def write(path,value):path.write_text(json.dumps(value,indent=2,sort_keys=True,allow_nan=False)+'\n')
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def errors(values):
    a=np.asarray(values,float)
    return None if not len(a) else {'n':len(a),'mae':float(np.mean(abs(a))),'rmse':float(np.sqrt(np.mean(a*a))),'bias':float(np.mean(a)),'medianAbsoluteError':float(np.median(abs(a)))}
def player_report(rows):
    groups={}
    for row in rows:
        for p in row['player']:groups.setdefault(p['stat'],[]).append(p)
    return {stat:{**errors([p['error'] for p in ps]),'coverage90':float(np.mean([p['coverage']['0.9']['covered'] for p in ps])),'baselineRows':sum(p.get('baseline') is not None for p in ps)} for stat,ps in groups.items()}
def diagnostics(rows):
    p=[r['homeProbability'] for r in rows];y=[r['actualHomeWin'] for r in rows]
    result={'games':len(rows),'moneyline':metrics(p,y),'teamScores':errors([s['error'] for r in rows for s in r['score']]),'margin':errors([r['margin']['error'] for r in rows]),'players':player_report(rows),'intervalCoverage':{str(q):float(np.mean([r['margin']['coverage'][str(q)]['covered'] for r in rows])) for q in [.5,.8,.9,.95]},'favorite':metrics([max(v,1-v) for v in p],[int((v>.5)==bool(a)) for v,a in zip(p,y)]),'confidentWrongGames':[r['gameId'] for r in rows if (r['homeProbability']>=.8 and r['actualHomeWin']==0) or (r['homeProbability']<=.2 and r['actualHomeWin']==1)],'maximumMonteCarloSEAt10000':.005}
    return result
def calibration(rows):
    output={}
    for method in ['temperature','platt','isotonic']:
        folds=[];raw=[];corrected=[];truth=[]
        for train,test in chronological_windows(rows):
            try:model=fit(method,[r['homeProbability'] for r in train],[r['actualHomeWin'] for r in train])
            except ValueError as error:folds.append({'status':'deferred','reason':str(error)});continue
            q=predict(model,[r['homeProbability'] for r in test]);ys=[r['actualHomeWin'] for r in test];ps=[r['homeProbability'] for r in test]
            folds.append({'trainGames':len(train),'heldOutGames':len(test),'trainEnd':max(r['eventStart'] for r in train),'heldOutStart':min(r['eventStart'] for r in test),'model':model,'raw':metrics(ps,ys),'corrected':metrics(q,ys),'simpleHistoricalBaseline':metrics([sum(r['actualHomeWin'] for r in train)/len(train)]*len(test),ys)})
            raw.extend(ps);corrected.extend(q);truth.extend(ys)
        if not truth:output[method]={'status':'deferred','folds':folds};continue
        delta=paired_interval((np.array(raw)-truth)**2,(np.array(corrected)-truth)**2)
        credible=bool(delta['bootstrap95'][1]<0 and all(f.get('corrected',{}).get('brier',1)<=f.get('raw',{}).get('brier',0) for f in folds))
        output[method]={'raw':metrics(raw,truth),'corrected':metrics(corrected,truth),'brierDelta':delta,'folds':folds,'improvesEveryWindowWithCrediblePooledBrier':credible,'promotionEligible':False,'reason':'Exploratory recalibration of reused development windows; fewer than 200 distinct training games, only two validation windows, and historical availability is unverified. No final test was used.'}
    return output

def nba_regularization(rows):
    """Diagnostic posterior-mean corrections; never coherent game forecasts."""
    results={}
    for prior in [5,20,80]:
        baseline=[];adjusted=[];windows=[];categories={}
        for train,test in chronological_windows(rows):
            grouped={}
            for r in train:
                for p in r['player']:
                    # Average within GAME first. Hundreds of correlated player
                    # rows are not treated as hundreds of independent games.
                    grouped.setdefault((p['stat'],p.get('position','unknown')),{}).setdefault(r['gameId'],[]).append(-p['error'])
            corrections={key:np.mean([np.mean(v) for v in games.values()])*len(games)/(len(games)+prior) for key,games in grouped.items()}
            original=[];new=[]
            for r in test:
                e=[];c=[]
                for p in r['player']:
                    e.append(p['error']);c.append(max(0.,p['mean']+corrections.get((p['stat'],p.get('position','unknown')),0))-p['actual']);group=categories.setdefault(p['stat'],{'reference':[],'corrected':[]});group['reference'].append(e[-1]);group['corrected'].append(c[-1])
                baseline.extend(e);adjusted.extend(c);original.append(float(np.mean(abs(np.array(e)))));new.append(float(np.mean(abs(np.array(c)))))
            windows.append({'games':len(test),'unweightedAcrossDifferentStatUnits':True,'gameMAEDelta':paired_interval(original,new)})
        results[str(prior)]={'reference':errors(baseline),'diagnosticCorrectedMeans':errors(adjusted),'byCategory':{stat:{'reference':errors(v['reference']),'corrected':errors(v['corrected'])} for stat,v in categories.items()},'windows':windows,'productionEligible':False,'reason':'Unit-mixed diagnostic only; no corrected minutes, joint distributions or player/team reconciliation. Cannot replace the basketball engine or support prop probabilities.'}
    return results

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--cpu-seconds',type=int,default=60);a=parser.parse_args()
    if not 1<=a.cpu_seconds<=120:parser.error('Use a 1..120 second local audit budget')
    if __import__('os').environ.get('VERCEL'):parser.error('Never run research on Vercel')
    resource.setrlimit(resource.RLIMIT_CPU,(a.cpu_seconds,a.cpu_seconds+1));start=time.monotonic();cpu=time.process_time()
    out=ROOT/'artifacts/calibration-v17';out.mkdir(exist_ok=True)
    protocol=json.loads((SOURCE/'protocol.json').read_text());selection=[g for g in protocol['selection'] if g['phase']=='validation']
    lock={'sourceProtocolSha256':sha(SOURCE/'protocol.json'),'eligibleGames':[g['id'] for g in selection],'excludedExposedFinalGames':sum(g['phase']=='test' for g in protocol['selection']),'methods':['regularized monotone Platt','temperature','isotonic PAVA'],'hyperparameterPolicy':'Predeclared fixed ridge=2; bounded training-NLL temperature fit; expanding chronological cohorts; no test optimization','minimumPromotionGames':200,'minimumIndependentValidationWindows':3,'maxCpuSeconds':a.cpu_seconds,'simulationsToRun':0,'productionPromotion':False}
    if (out/'protocol.json').exists() and json.loads((out/'protocol.json').read_text())!=lock:raise RuntimeError('Existing audit protocol differs; use a new version')
    write(out/'protocol.json',lock)
    report={'protocol':lock,'leagues':{},'newGamesSimulated':0,'newCompleteGames':0,'modelsPromoted':[],'sourceForecastsChanged':0,'finalTestUsed':False,'stop':'available_development_evidence_exhausted; insufficient independent windows for promotion','limitations':['All results reuse development games and are exploratory.','CFB/NFL injury, lineup, weather publication archives remain incomplete.','NBA minute/rotation causal errors cannot be established from these evaluations; actual minute fields are absent from these evaluation rows; the separate minute audit uses original raw box-score records.','No historical executable prop lines were available. Fixed diagnostic threshold grids are not historical betting markets.','No claim of player-prop calibration improvement; game clustering is required for correlated observations.']}
    for sport in ['NFL','CFB','NBA']:
        ids={g['id'] for g in selection if g['sport']==sport};by_candidate={};hashes={}
        for candidate in [c['id'] for c in protocol['candidates']]:
            rows=[]
            for game_id in sorted(ids):
                name=game_id.replace(':','_')+'.evaluation.json.gz';path=SOURCE/'runs'/candidate/sport/name
                if not path.exists():continue
                row=read(path)
                if row['phase']!='validation' or row['gameId']!=game_id or row['actualHomeWin'] not in (0,1):raise RuntimeError('Evaluation identity/phase mismatch')
                rows.append(row);hashes[str(path.relative_to(ROOT))]=sha(path)
            if rows:by_candidate[candidate]=rows
        ref=by_candidate['reference-v15'];comparisons={}
        for candidate,rows in by_candidate.items():
            lookup={r['gameId']:r for r in rows};pairs=[(r,lookup[r['gameId']]) for r in ref if r['gameId'] in lookup]
            comparisons[candidate]={'diagnostic':diagnostics(rows),'calibrationCandidates':calibration(rows),'pairedBrierDelta':paired_interval([r['brier'] for r,c in pairs],[c['brier'] for r,c in pairs]),'pairedScoreMAEDelta':paired_interval([np.mean([abs(s['error']) for s in r['score']]) for r,c in pairs],[np.mean([abs(s['error']) for s in c['score']]) for r,c in pairs])}
        report['leagues'][sport]={'distinctGames':len(ref),'sourceForecastVersions':sum(map(len,by_candidate.values())),'engineConfigurationsAudited':len(by_candidate),'calibrationFamiliesPerEngine':3,'comparisons':comparisons,'nbaRegularizationDiagnostics':nba_regularization(ref) if sport=='NBA' else None,'sourceChecksums':hashes,'prospectivelyQualifiedGames':0}
    report['resources']={'cpuSeconds':time.process_time()-cpu,'wallSeconds':time.monotonic()-start,'peakRssKiB':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'hostingCpuSeconds':0,'providerRequests':0,'simulationRuns':0}
    write(out/'report.json',report);write(ROOT/'docs/reports/calibration-v17.json',report)
    print(json.dumps({'distinctGames':{s:v['distinctGames'] for s,v in report['leagues'].items()},'resources':report['resources'],'stop':report['stop'],'promotions':[]}))
if __name__=='__main__':main()
