"""Gated, resumable 500-game regression audit. No final-period model tuning.

The old 500-game cohort is exposed development evidence. New forecasts freeze
before grading. No closing line is invented; CLV stays null without quotes.
"""
import sys,json,gzip,pickle,hashlib,time,resource,signal
from pathlib import Path
from collections import defaultdict,Counter
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import numpy as np
from modeling.football_v15 import fit_football,simulate_football,VERSION
from modeling.football_transitions_v18 import migrate
from modeling.football_source_v18 import transition_evidence,augment_rows,eligible_training
from modeling.football_data_v15 import training_before,NORMALIZER_VERSION
from modeling.overnight_v20.state import read,atomic,digest
from modeling.iterative_learning import freeze_json
from modeling.integration_v22.datasets import protected
OUT=ROOT/'artifacts/market-v18/r5';SEED=180018
def code():return {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),*[ROOT/'modeling'/n for n in ['football_v15.py','football_v15_legacy.py','football_transitions_v18.py','football_source_v18.py','simulator.py','fit.py']]]}
def selection():
    inventory=read(ROOT/'docs/reports/v15-validation.json')['inventory'];chosen={}
    for row in inventory:
        if row['sport'] not in ('NFL','CFB'):continue
        gid=row['gameId']
        if gid not in chosen or row['modelVersion'].endswith('15.1.0'):chosen[gid]=row
    if len(chosen)!=500 or set(chosen)&protected():raise ValueError('Original 500-game cohort mismatch or protected overlap')
    for gid,row in chosen.items():
        directory=ROOT/'artifacts/engine-v15'/('candidate-hurdle/runs' if row['modelVersion'].endswith('15.1.0') else 'runs');p=directory/(gid.replace(':','_')+'.json.gz')
        if not p.exists():p=directory/(gid.replace(':','_')+'.gz')
        forecast=load(p)['result'];row['originalModelSHA256']=forecast['inputDataVersion'];row['originalSeed']=forecast['seed']
        if forecast['simulations']!=10000:raise ValueError('Original workload differs; do not reduce simulations')
    return sorted(chosen.values(),key=lambda r:(r['sport'],r['fitCutoff'],r['gameId']))
def register():
    freeze_json(OUT/'audit-protocol.json',{'version':VERSION,'scope':'exposed_500_game_regression_not_untouched_accuracy','selection':selection(),'code':code(),'simulationsPerGame':10000,'seedPolicy':'Each game retains its original frozen forecast seed','coefficientsRefit':False,'marketPricesInvented':False,'primaryMarketMetric':'CLV','CLV':None,'tuningOnThisCohort':False,'productionPromotion':False});print('Registered original 500 games; 10,000 full games each')
def load(path):return json.loads(gzip.decompress(path.read_bytes()))
def actual(row):
    roots=[ROOT/'artifacts/engine-v15/candidate-hurdle/runs',ROOT/'artifacts/engine-v15/runs']
    for base in roots:
        p=base/(row['gameId'].replace(':','_')+'.json.summary.json')
        # Historical writer uses target.with_suffix('.summary.json').
        alternatives=[p,base/(row['gameId'].replace(':','_')+'.summary.json')]
        for p in alternatives:
            d=read(p)
            if d and d.get('modelVersion',row['modelVersion'])==row['modelVersion'] and hashlib.sha256(p.read_bytes()).hexdigest()==row['summarySha256']:return d
    for base in roots:
        for p in base.glob('*.summary.json'):
            if hashlib.sha256(p.read_bytes()).hexdigest()==row['summarySha256']:return read(p)
    raise ValueError('Matching immutable final/stat summary is unavailable')
def run(smoke=False):
    protocol=read(OUT/'audit-protocol.json')
    if not protocol or protocol['code']!=code():raise ValueError('Audit source differs from its frozen protocol; create a new revision')
    selected=protocol['selection'];selected=[next(r for r in selected if r['sport']==s) for s in ['NFL','CFB']] if smoke else selected;groups=defaultdict(list)
    for row in selected:groups[(row['sport'],row['fitCutoff'])].append(row)
    started=time.monotonic();cpu=time.process_time();completed=[];errors=[];raw_cache={};loaded_sport=None;dataset=None;banned=protected()
    def stop(sig,frame):raise TimeoutError('Local bounded audit stopped; completed games are resumable')
    signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGALRM,stop);signal.alarm(3000);resource.setrlimit(resource.RLIMIT_CPU,(int(cpu)+2400,int(cpu)+2405));resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3))
    try:
        for (sport,cutoff),matchups in groups.items():
            if all((OUT/'runs'/(r['gameId'].replace(':','_')+'.summary.json')).exists() for r in matchups):continue
            if loaded_sport!=sport:
                raw_cache.clear();dataset=pickle.load((ROOT/f'artifacts/engine-v15/{sport}-{NORMALIZER_VERSION}.cache').open('rb'));loaded_sport=sport
            rows=eligible_training(training_before(dataset,cutoff),cutoff,banned)
            paths=[Path('/tmp/gridiron-'+('nfl-pbp-' if sport=='NFL' else 'cfb-public-pbp-')+str(y)+'.parquet') for y in (2024,2025)];evidence=transition_evidence(paths,sport,cutoff,raw_cache);pos=[ROOT/'artifacts/fullgame-v23/sources/stats_player_week_2024.parquet',ROOT/'artifacts/dynamic-v24/completion-r4/additional-nfl-sources/stats_player_week_2025.parquet'] if sport=='NFL' else [];rows=augment_rows(rows,evidence,pos);source=digest({'raw':evidence['sourceVersion'],'cutoff':cutoff,'normalizer':NORMALIZER_VERSION});model_path=OUT/'models'/(sport+'-'+cutoff[:10]+'.json.gz')
            if model_path.exists():model=load(model_path)
            else:
                originals=[]
                for directory in [ROOT/'artifacts/engine-v15/models',ROOT/'artifacts/engine-v15/candidate-hurdle/models']:
                    for file in directory.glob(sport+'-'+cutoff[:10]+'*.gz'):
                        original=load(file)
                        if original.get('fittingCutoff')==cutoff:originals.append(original)
                if not originals:raise ValueError('Original fitted coefficients unavailable for this exact cutoff')
                # Each historical family is preserved. Multiple versions at a
                # cutoff require a separate immutable artifact per version.
                model={m['sha256']:migrate(m,rows,evidence) for m in originals};freeze_json(model_path,model)
            for row in matchups:
                gid=row['gameId'];target=OUT/'runs'/(gid.replace(':','_')+'.json.gz');summary=target.with_suffix('.summary.json')
                if summary.exists():continue
                try:
                    chosen=model[row['originalModelSHA256']];game=dataset['games'][gid];assert gid not in chosen['trainingGameIds'];assert all(r['at']<row['eventStart'] for r in rows);begin=time.process_time()
                    forecast=load(target)['forecast'] if target.exists() else simulate_football(chosen,game['home'],game['away'],row['eventStart'],10000,row['originalSeed'],batch_size=2000,representative_games=0)
                    freeze_json(target,{'forecast':forecast,'modelVersion':VERSION,'code':protocol['code'],'mode':'conditional_exposed_regression','finalsUsedAsInputs':False})
                    # Only after immutable forecast exists do we open final labels.
                    reference=actual(row);scores=reference['actualScore'];p=forecast['homeWinProbability'];y=int(scores[0]>scores[1]);pred=[forecast['scoreDistributions'][t]['mean'] for t in [game['home'],game['away']]];errors_now=[pred[i]-scores[i] for i in (0,1)];player=[]
                    for observed in reference.get('playerErrors',[]):
                        dist=forecast['players'].get(observed['id'],{}).get(observed['stat'])
                        if dist:player.append({'id':observed['id'],'stat':observed['stat'],'error':dist['mean']-observed['actual'],'oldError':observed['error'],'covered90':dist['interval90'][0]<=observed['actual']<=dist['interval90'][1]})
                    result={'gameId':gid,'sport':sport,'baselineVersion':row['modelVersion'],'modelVersion':VERSION,'scoreErrors':errors_now,'baselineScoreErrors':reference['scoreErrors'],'brier':(p-y)**2,'baselineBrier':reference['brier'],'logLoss':-np.log(max(1e-15,p if y else 1-p)),'baselineLogLoss':reference['logLoss'],'players':player,'simulations':10000,'samplingSeed':row['originalSeed'],'CLV':None,'prices':None,'accountingReconciled':forecast['quality']['allGamesAccountingReconciled'],'strictPregameQualified':False,'transitionCoverage':{'returnEvents':{k:{a:b for a,b in v.items() if a!='returnYards'} for k,v in chosen['transitions']['returnTouchdowns'].items()},'typedStarts':{k:{t:len(v) for t,v in pools.items()} for k,pools in chosen['transitions']['starts'].items()},'conversionContext':chosen['transitions']['twoPointDecision']['contextual']},'cpuSeconds':time.process_time()-begin,'frozenForecastSHA256':hashlib.sha256(target.read_bytes()).hexdigest()};atomic(summary,result);completed.append(gid);print(json.dumps({'completed':gid,'gamesThisProcess':len(completed),'accounting':True}),flush=True)
                except (ValueError,AssertionError,KeyError) as e:
                    error={'gameId':gid,'error':str(e)};errors.append(error);atomic(OUT/'failures'/(gid.replace(':','_')+'.json'),error);print(json.dumps(error),flush=True)
            del rows,evidence,model
    finally:
        signal.alarm(0);atomic(OUT/('smoke-receipt.json' if smoke else 'audit-receipt.json'),{'completedThisInvocation':len(completed),'errors':errors,'cpuSeconds':time.process_time()-cpu,'wallSeconds':time.monotonic()-started,'smoke':smoke,'productionWrites':0})
    return summarize()
def summarize():
    rows=[read(p) for p in (OUT/'runs').glob('*.summary.json')];groups={}
    for sport in ['NFL','CFB']:
        gs=[r for r in rows if r['sport']==sport]
        if not gs:continue
        groups[sport]={'games':len(gs),'newScoreMAE':float(np.mean([abs(e) for r in gs for e in r['scoreErrors']])),'originalScoreMAE':float(np.mean([abs(e) for r in gs for e in r['baselineScoreErrors']])),'newBrier':float(np.mean([r['brier'] for r in gs])),'originalBrier':float(np.mean([r['baselineBrier'] for r in gs])),'newLogLoss':float(np.mean([r['logLoss'] for r in gs])),'originalLogLoss':float(np.mean([r['baselineLogLoss'] for r in gs])),'baselineVersions':dict(Counter(r['baselineVersion'] for r in gs))}
    result={'gamesCompleted':len(rows),'targetGames':500,'allAccountingReconciled':all(r['accountingReconciled'] for r in rows),'simulatedCompleteGames':sum(r['simulations'] for r in rows),'CLV':None,'strictPregameGames':0,'tunedOnAudit':False,'gate1AuditComplete':len(rows)==500,'groups':groups,'comparisonWarning':'Original baseline mixes v15.0 and v15.1; version-specific deltas are required before any causal claim. Exposed regression cohort is not new accuracy evidence.'};atomic(OUT/'audit-results.json',result);return result
if __name__=='__main__':
    if '--register' in sys.argv:register()
    elif '--summary' in sys.argv:print(json.dumps(summarize()))
    else:print(json.dumps(run('--smoke' in sys.argv)))
