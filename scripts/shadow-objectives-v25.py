"""Bounded A/B/C scoring on the SAME original immutable V24 forecast traces.

Reuses the frozen V25 replay implementation; no duplicate tournament, refitting,
new cohort, new full-game simulation, market creation or source overwrite.
"""
import sys,json,time,hashlib,importlib.util,contextlib,resource,signal,fcntl
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from modeling.accuracy_v25.shadow import FrozenShadow
from modeling.accuracy_v25.objectives import AccuracyMode
from modeling.iterative_learning import freeze_json
from modeling.overnight_v20.state import read,atomic,digest

OUT=ROOT/'artifacts/accuracy-v25/objectives-r1'
UPSTREAM=ROOT/'scripts/replay-accuracy-v25.py'
CODE=[Path(__file__),ROOT/'modeling/accuracy_v25/shadow.py',ROOT/'modeling/accuracy_v25/objectives.py',ROOT/'modeling/accuracy_v25/market_research.py',ROOT/'modeling/router.py']


def register():
    if not read(ROOT/'artifacts/accuracy-v25/stage2-r2/receipt.json',{}).get('passed'):
        raise ValueError('Original frozen V25 evaluation must pass first')
    freeze_json(OUT/'protocol.json',{'version':'three-objective-shadow-25.2','scope':'conditional_corrected_history',
        'code':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in CODE+[UPSTREAM]},
        'sourceProtocolSHA256':hashlib.sha256((ROOT/'artifacts/accuracy-v25/stage2-r2/protocol.json').read_bytes()).hexdigest(),
        'registrySHA256':hashlib.sha256((ROOT/'docs/research/specialized-v24-registry.json').read_bytes()).hexdigest(),
        'sameEventsForEveryMode':True,'modelSelectionAllowed':False,'fittingAllowed':False,
        'protectedFinalOutcomesAllowed':False,'newIndependentGames':0,'newFullGameSimulations':0,
        'marketInformation':'No verified historical quote cohort configured; null, never invented',
        'computeBudget':{'cpuSeconds':180,'wallSeconds':360,'addressSpaceGiB':4,'parallelism':1},
        'reservationMeaning':'Newly requested bounded implementation verification; previous campaign ledger and pause gates remain unchanged'})


def run():
    protocol=read(OUT/'protocol.json')
    if not protocol:raise ValueError('Register immutable objective protocol first')
    for name,sha in protocol['code'].items():
        if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=sha:raise ValueError('Frozen objective code changed')
    for name,key in [('artifacts/accuracy-v25/stage2-r2/protocol.json','sourceProtocolSHA256'),('docs/research/specialized-v24-registry.json','registrySHA256')]:
        if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=protocol[key]:raise ValueError('Original protocol/registry changed')
    spec=importlib.util.spec_from_file_location('frozen_v25_replay_for_objectives',UPSTREAM)
    baseline=importlib.util.module_from_spec(spec);spec.loader.exec_module(baseline)
    original_score=baseline.score_frozen;collected=[];upstream_result={};last={}
    def freeze_copy(path,value):
        relative=path.relative_to(baseline.OUT)
        last.clear();last.update(relative=relative,value=value)
        return freeze_json(OUT/'original-replay-copies'/relative,value)
    def shadow_score(rows,point,draws,thresholds):
        parts=last['relative'].parts;sport=parts[1];provenance=last['value']
        ids=[{'sport':sport,'gameId':r['gameId'],'team':r['team'],'player':r['player'],'stat':r['stat']} for r in rows]
        frozen=FrozenShadow(ids,point,draws,model_version=provenance['sourceModelSHA256'],provenance=provenance)
        # Freeze the new envelope before joining outcomes. The underlying point
        # forecast was originally frozen by the upstream replay before grading.
        freeze_json(OUT/'snapshots'/last['relative'],frozen.snapshot|{'sha256':frozen.snapshot_hash})
        modes=frozen.evaluate([i|{'y':r['y']} for i,r in zip(ids,rows)],thresholds=thresholds)
        assert len({m['eventSetHash'] for m in modes.values()})==1
        assert len({m['snapshotHash'] for m in modes.values()})==1
        freeze_json(OUT/'mode-results'/last['relative'],modes)
        a=modes[AccuracyMode.PROBABILITY.value]['prediction'];b=modes[AccuracyMode.NUMERICAL.value]['prediction']
        collected.append({'sport':sport,'stat':rows[0]['stat'],'window':int(parts[2]),'family':parts[4].removesuffix('-replay.json'),
                          'games':len({r['gameId'] for r in rows}),'observations':len(rows),'snapshotHash':frozen.snapshot_hash,
                          'eventSetHash':frozen.event_hash,'predictionHashes':{k:v['predictionHash'] for k,v in modes.items()},
                          'modeA':{k:a.get(k) for k in ('brier','logLoss','ece','crps','scope')},
                          'modeB':b,'modeC':modes[AccuracyMode.MARKET.value]['prediction'],
                          'jointRealizations':False,'newIndependentAccuracyClaim':False})
        return original_score(rows,point,draws,thresholds)
    baseline.freeze_json=freeze_copy;baseline.score_frozen=shadow_score
    baseline.atomic=lambda path,value:upstream_result.update(value)
    with (OUT/'replay.log').open('w') as log,contextlib.redirect_stdout(log):
        summary=baseline.run()
    if len(collected)!=summary['modelWindowTracesReplayed'] or len(collected)!=len(upstream_result['checks']):
        raise ValueError('Objective/replay trace cardinality mismatch')
    result={'version':protocol['version'],'scope':protocol['scope'],'traces':collected,
            'traceCount':len(collected),'categories':summary['categoriesReplayed'],
            'sameEventSetChecksPassed':len(collected),'sameSnapshotChecksPassed':len(collected),
            'separateModePredictionHashes':True,'marketObservations':0,'marketBlendFits':0,
            'newIndependentGames':0,'newStrictPregameGames':0,'newFullGameSimulations':0,
            'newModelFits':0,'protectedFinalOutcomesOpened':False,'productionWrites':0,
            'modelsPromoted':0,'baselineReplayPassed':True,'forecastingGatePassed':False,
            'originalRegistrySHA256':protocol['registrySHA256']}
    freeze_json(OUT/'results.json',result)
    return {k:v for k,v in result.items() if k!='traces'}


if __name__=='__main__':
    if '--register' in sys.argv:register()
    else:
        OUT.mkdir(parents=True,exist_ok=True)
        with (OUT/'runner.lock').open('a') as lease:
            fcntl.flock(lease,fcntl.LOCK_EX|fcntl.LOCK_NB)
            start=time.monotonic();cpu=time.process_time();receipt={'passed':False}
            def stop(sig,frame):raise TimeoutError('Bounded objective verification stopped')
            signal.signal(signal.SIGALRM,stop);signal.alarm(360)
            resource.setrlimit(resource.RLIMIT_CPU,(180,185));resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3))
            try:receipt.update(run());receipt['passed']=True
            except Exception as e:receipt.update(error=type(e).__name__,reason=str(e));raise
            finally:
                signal.alarm(0);receipt.update(cpuSeconds=time.process_time()-cpu,wallSeconds=time.monotonic()-start,peakRssKiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
                atomic(OUT/'receipt.json',receipt);print(json.dumps(receipt),flush=True)
