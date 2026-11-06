"""V25 Gate 2: frozen per-category inference and metric reconstruction.

Reuses V24 models, feature preparation, seeds and scoring; never fits or chooses
a new family. Private inputs stay private. Previously exposed windows are replay
cohorts, not new validation or untouched final tests.
"""
import sys,json,gzip,pickle,hashlib,time,resource,signal,gc
from pathlib import Path
from collections import defaultdict,Counter
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import numpy as np
from modeling.dynamic_v24.completion.data import packets,enrich_packets,features_only
from modeling.dynamic_v24.completion.additional_data import packets as nfl_history
from modeling.dynamic_v24.completion.efficient_data import records
from modeling.accuracy_v25.evaluation import feature_guard,score_frozen
from modeling.iterative_learning import freeze_json
from modeling.overnight_v20.state import read,atomic,digest

OUT=ROOT/'artifacts/accuracy-v25/stage2-r2'
METRICS=('mae','rmse','bias','medianAbsoluteError','interval90Coverage','crps',
         'zeroEventBrier','zeroEventECE','cdfBrier','cdfLogLoss','cdfECE','observations','games','brier','logLoss')

def payload(path):return json.loads(gzip.decompress(path.read_bytes()))

def dates(folder,family):
    snapshot=payload(folder/(family+'-forecast.json.gz'))
    values=[snapshot[k] for k in ('trainingThrough','residualCalibrationThrough','selectionThrough') if snapshot.get(k)]
    for component in snapshot.get('components',[]):values.extend(dates(folder,component))
    if not values:raise ValueError('Original model availability timestamps unavailable')
    return values

def register():
    if not read(ROOT/'artifacts/accuracy-v25/stage1/gate1-receipt.json',{}).get('passed'):raise ValueError('Gate 1 required')
    paths=[Path(__file__),ROOT/'modeling/accuracy_v25/evaluation.py',ROOT/'modeling/dynamic_v24/completion/selection.py']
    heads=read(ROOT/'docs/research/specialized-v24-results.json')['heads'];sources={}
    for sport,folder in {(h['sport'],h['protocol']) for h in heads}:
        base=ROOT/'artifacts/dynamic-v24'/folder
        for p in [base/'protocol.json',base/'registry.json',base/sport/'leaderboard.json',*[base/sport/str(i)/'results.json' for i in (0,1)]]:
            sources[str(p.relative_to(ROOT))]=hashlib.sha256(p.read_bytes()).hexdigest()
    freeze_json(OUT/'protocol.json',{'operation':'frozen_conditional_metric_replay','code':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
        'inputReportsAndCohorts':sources,'revisionReason':'Bind original report/cohort editions and reject unknown final-test exposure; statistical prediction law unchanged',
        'leaderboardSHA256':hashlib.sha256((ROOT/'docs/research/specialized-v24-results.json').read_bytes()).hexdigest(),
        'primaryHeads':read(ROOT/'docs/research/specialized-v24-results.json')['heads'],
        'modelSelectionAllowed':False,'trainingAllowed':False,'evidenceTier':'conditional_corrected_history',
        'pointAndIntervalTolerance':1e-12,'metricTolerance':1e-10,'distributionSeedPolicy':'Original frozen snapshot seed and marginal draw count',
        'confidenceIntervalMethod':'V24 original paired game-clustered bootstrap, 20,000 replicates, alpha .05/159; no new selections',
        'protectedFinalOutcomesAllowed':False,'newIndependentGames':0})

def run():
    spec=read(OUT/'protocol.json')
    if not spec:raise ValueError('Freeze Gate 2 replay protocol first')
    for name,sha in spec['code'].items():
        if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=sha:raise ValueError('Registered replay code changed')
    for name,sha in spec['inputReportsAndCohorts'].items():
        if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=sha:raise ValueError('Original cohort/report edition changed')
    if hashlib.sha256((ROOT/'docs/research/specialized-v24-results.json').read_bytes()).hexdigest()!=spec['leaderboardSHA256']:raise ValueError('V24 leaderboard edition changed')
    groups=defaultdict(list)
    for head in spec['primaryHeads']:groups[(head['sport'],head['protocol'])].append(head['stat'])
    checked=[];unavailable=[];category_games=defaultdict(set)
    for (sport,folder),stats in groups.items():
        path=ROOT/'artifacts/dynamic-v24'/folder;protocol=read(path/'protocol.json');windows=protocol['selection'][sport]
        selected={g for w in windows for g in w['games']};extra=sport=='NFL' and folder!='completion-r4'
        gs=nfl_history('NFL') if extra else packets(sport)
        if extra:gs=[g for g in gs if g['at']<'2022-01-01']
        rejected={r['gameId'] for r in protocol.get('sourceRejectedGames',[])}
        gs=enrich_packets([g for g in gs if g['id'] not in rejected and g['at']<max(w['end'] for w in windows)],sport)
        rows=records(gs,sport,selected)
        for wi,w in enumerate(windows):
            reports=read(path/sport/str(wi)/'results.json');ids=set(w['games'])
            for stat in stats:
                report=reports.get(stat)
                if not report or not report.get('modelArtifacts'):
                    unavailable.append({'sport':sport,'stat':stat,'window':wi,'reason':'Original V24 had no supported fitted baseline; no replacement invented'});continue
                future=[r for r in rows if r['stat']==stat and r['gameId'] in ids];x=features_only(future)
                usable=np.array([i for i,r in enumerate(future) if r['y'] is not None],dtype=int)
                if not len(usable):raise ValueError('Original baseline has no reproducible grading observations')
                for family in sorted({'rolling5',*report['selected'].values()}):
                    artifact=report['modelArtifacts'].get(family)
                    if artifact is None:
                        unavailable.append({'sport':sport,'stat':stat,'window':wi,'family':family,'reason':'Original fixed family unavailable; no substitution'});continue
                    model_path=ROOT/artifact['path'];raw=model_path.read_bytes()
                    if hashlib.sha256(raw).hexdigest()!=artifact['sha256']:raise ValueError('Model artifact checksum mismatch')
                    old=payload(model_path.parent/(family+'-forecast.json.gz'))
                    if digest(x)!=old['featureInputHash']:raise ValueError('Original feature digest differs: '+sport+'/'+stat+'/'+str(wi))
                    if [r['gameId'] for r in x]!=old['gameIds'] or [r['player'] for r in x]!=old['playerIds'] or [r['team'] for r in x]!=old['teamIds']:raise ValueError('Frozen identity/order differs')
                    feature_guard(x,max(dates(model_path.parent,family)),evidence_tier=spec['evidenceTier'])
                    model=pickle.loads(raw);point=model.predict(x);draws=model.samples(x,old.get('seed',protocol['seed']),old.get('marginalDistributionDraws',protocol['distributionDraws']))
                    np.testing.assert_allclose(point,old['pointEstimate'],rtol=1e-12,atol=1e-12)
                    interval=np.quantile(draws,[.05,.95],axis=1).T;np.testing.assert_allclose(interval,old['interval90'],rtol=1e-12,atol=1e-12)
                    target=OUT/folder/sport/str(wi)/stat/(family+'-replay.json')
                    freeze_json(target,{'featureDigest':digest(x),'pointDigest':digest(point.tolist()),'intervalDigest':digest(interval.tolist()),'sourceModelSHA256':artifact['sha256'],'sourceForecastSHA256':hashlib.sha256((model_path.parent/(family+'-forecast.json.gz')).read_bytes()).hexdigest(),'seed':old.get('seed',protocol['seed']),'draws':draws.shape[1],'currentLabelsReadByPrediction':False})
                    # Predictions/intervals are now frozen, before joining labels.
                    grade=[future[i] for i in usable];scores=score_frozen(grade,point[usable],draws[usable],report['candidates'][family]['thresholds']);expected=report['candidates'][family]
                    for key in METRICS:
                        if key in expected and expected[key] is not None:np.testing.assert_allclose(scores[key],expected[key],rtol=1e-10,atol=1e-10,err_msg=sport+'/'+stat+'/'+family+'/'+key)
                    for level,value in expected['coverage'].items():np.testing.assert_allclose(scores['coverage'][level],value,rtol=1e-10,atol=1e-10)
                    checked.append({'sport':sport,'stat':stat,'window':wi,'family':family,'games':scores['games'],'observations':scores['observations'],'metrics':scores,'pointAndIntervalReplayed':True,'metricReplayPassed':True})
                    category_games[sport+':'+stat].update(r['gameId'] for r in grade)
                print(json.dumps({'sport':sport,'stat':stat,'window':wi,'replayed':True}),flush=True)
        del gs,rows;gc.collect()
    result={'gate':2,'passed':True,'scope':spec['evidenceTier'],'checks':checked,'unsupported':unavailable,'categoriesReplayed':len(category_games),'categoriesAudited':len(spec['primaryHeads']),'gradedGamesByCategory':{k:len(v) for k,v in category_games.items()},'strictPregameGames':0,'newIndependentGames':0,'modelsFit':0,'gameSimulations':0,'protectedFinalOutcomesOpened':False,'productionWrites':0,'probabilityPromotion':False}
    atomic(OUT/'results.json',result);return {'gate':2,'passed':True,'modelWindowTracesReplayed':len(checked),'categoriesReplayed':len(category_games),'unsupportedStatuses':len(unavailable),'newIndependentGames':0,'modelsFit':0,'gameSimulations':0}

if __name__=='__main__':
    if '--register' in sys.argv:register()
    else:
        start=time.monotonic();cpu=time.process_time();receipt={'gate':2,'passed':False}
        def stop(sig,frame):raise TimeoutError('Bounded Gate 2 replay stopped')
        signal.signal(signal.SIGALRM,stop);signal.alarm(600);resource.setrlimit(resource.RLIMIT_CPU,(300,305));resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3))
        try:receipt.update(run())
        except Exception as e:receipt.update(error=type(e).__name__,reason=str(e));raise
        finally:
            signal.alarm(0);receipt.update(cpuSeconds=time.process_time()-cpu,wallSeconds=time.monotonic()-start,peakRssKiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss);atomic(OUT/'receipt.json',receipt);print(json.dumps(receipt),flush=True)
