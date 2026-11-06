"""Diagnostic fixed-model ablations; no training or new winner selection."""
import sys,json,gzip,pickle,hashlib,time,resource,signal
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import numpy as np
from modeling.dynamic_v24.completion.data import packets,enrich_packets,features_only
from modeling.dynamic_v24.completion.additional_data import packets as nfl_history
from modeling.dynamic_v24.completion.efficient_data import records
from modeling.dynamic_v24.completion.selection import paired_loss
from modeling.accuracy_v25.evaluation import feature_guard
from modeling.accuracy_v25.leakage import shuffle_control
from modeling.overnight_v20.state import read,atomic,digest
from modeling.iterative_learning import freeze_json
OUT=ROOT/'artifacts/accuracy-v25/stage3-r3'
CASES=[('NFL','completion-nfl-extension-r2',['passingYards']),('CFB','completion-cfb-extension-r1',['passingYards']),('NBA','completion-nba-clean-r1',['rebounds','steals'])]

def payload(path):return json.loads(gzip.decompress(path.read_bytes()))

def register():
    if not read(ROOT/'artifacts/accuracy-v25/stage2-r2/receipt.json',{}).get('passed'):raise ValueError('Gate 2 required')
    paths=[Path(__file__),ROOT/'modeling/accuracy_v25/leakage.py',ROOT/'modeling/accuracy_v25/evaluation.py'];sources={}
    for sport,folder,stats in CASES:
        p=ROOT/'artifacts/dynamic-v24'/folder
        for f in [p/'protocol.json',p/sport/'0/results.json']:sources[str(f.relative_to(ROOT))]=hashlib.sha256(f.read_bytes()).hexdigest()
    freeze_json(OUT/'protocol.json',{'cases':CASES,'window':0,'code':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},'reports':sources,'seed':250025,'controls':['team_score_context','player_identity','future_history'],'marketControl':'unavailable_no_verified_historical_market_features','refitsAllowed':False,'winnerSelectionAllowed':False,'scope':'previously_exposed_conditional_diagnostic','protectedOutcomesAllowed':False})

def run():
    spec=read(OUT/'protocol.json')
    for name,sha in {**spec['code'],**spec['reports']}.items():
        if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=sha:raise ValueError('Control protocol edition changed')
    results=[]
    for sport,folder,stats in spec['cases']:
        p=ROOT/'artifacts/dynamic-v24'/folder;protocol=read(p/'protocol.json');w=protocol['selection'][sport][0];gs=nfl_history('NFL') if sport=='NFL' else packets(sport)
        if sport=='NFL':gs=[g for g in gs if g['at']<'2022-01-01']
        bad={r['gameId'] for r in protocol.get('sourceRejectedGames',[])};gs=enrich_packets([g for g in gs if g['id'] not in bad and g['at']<w['end']],sport);rr=records(gs,sport,set(w['games']));reports=read(p/sport/'0/results.json')
        for stat in stats:
            report=reports[stat];family=report['selected']['expected_value'];artifact=report['modelArtifacts'][family];model_path=ROOT/artifact['path'];raw=model_path.read_bytes()
            if hashlib.sha256(raw).hexdigest()!=artifact['sha256']:raise ValueError('Control model checksum mismatch')
            old=payload(model_path.parent/(family+'-forecast.json.gz'));frame=[r for r in rr if r['stat']==stat and r['gameId'] in set(w['games'])];x=features_only(frame)
            if digest(x)!=old['featureInputHash']:raise ValueError('Control baseline features differ from original')
            model=pickle.loads(raw);baseline=model.predict(x);np.testing.assert_allclose(baseline,old['pointEstimate'],atol=1e-12,rtol=1e-12)
            grade=np.array([i for i,r in enumerate(frame) if r['y'] is not None]);labels=[frame[i] for i in grade]
            point=getattr(model,'point',model);encoder=getattr(point,'encoder',None);known=set(encoder.categories_[0]) if encoder is not None else set()
            for control in ('team_score_context','player_identity','future_history'):
                changed=shuffle_control(x,control,spec['seed'])
                if control=='future_history':
                    rejected=False
                    try:feature_guard(changed,report['trainingThrough'],evidence_tier='conditional_corrected_history')
                    except ValueError:rejected=True
                    if not rejected:raise ValueError('Shifted future features were accepted')
                    results.append({'sport':sport,'stat':stat,'family':family,'control':control,'rejectedBeforePrediction':True,'games':len({r['gameId'] for r in labels})});continue
                predicted=model.predict(changed);freeze_json(OUT/(sport+'-'+stat+'-'+control+'.json'),{'featureDigest':digest(changed),'pointDigest':digest(predicted.tolist()),'modelSHA256':artifact['sha256'],'labelsUsedByPrediction':False})
                y=np.array([r['y'] for r in labels]);before=baseline[grade];after=predicted[grade];paired=paired_loss(labels,before,after,loss='absolute',alpha=.05,seed=spec['seed'],bootstraps=2000);same=bool(np.allclose(before,after,rtol=1e-12,atol=1e-12))
                results.append({'sport':sport,'stat':stat,'family':family,'control':control,'games':len({r['gameId'] for r in labels}),'observations':len(labels),'baselineMAE':float(np.mean(abs(before-y))),'controlMAE':float(np.mean(abs(after-y))),'pairedGameMAEDelta':paired,'identicalPredictions':same,'maximumPointChange':float(np.max(abs(after-before))),'identityEncoderPresent':encoder is not None,'knownPlayerFraction':float(np.mean([r['player'] in known for r in x])) if known else None,'interpretation':'No effect: this fixed family does not use the perturbed identity/context under these inputs' if same else 'Ablation changes predictions; interval is exploratory sensitivity evidence, not a candidate improvement or causal effect'})
    result={'gate':3,'hardTemporalControlsPassed':True,'controls':results,'marketControl':{'status':'unavailable','reason':'No verified historical market features; no synthetic prices introduced'},'newFits':0,'newIndependentGames':0,'productionWrites':0,'promotion':False};atomic(OUT/'results.json',result);return {'controlsExecuted':len(results),'futureHistoryRejections':sum(r.get('rejectedBeforePrediction',False) for r in results),'newFits':0}

if __name__=='__main__':
    if '--register' in sys.argv:register()
    else:
        start=time.monotonic();cpu=time.process_time();receipt={'gate':3,'passed':False}
        def stop(sig,frame):raise TimeoutError('Bounded control replay stopped')
        signal.signal(signal.SIGALRM,stop);signal.alarm(300);resource.setrlimit(resource.RLIMIT_CPU,(180,185));resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3))
        try:receipt.update(run(),passed=True)
        except Exception as e:receipt.update(error=type(e).__name__,reason=str(e));raise
        finally:
            signal.alarm(0);receipt.update(cpuSeconds=time.process_time()-cpu,wallSeconds=time.monotonic()-start,peakRssKiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss);atomic(OUT/'receipt.json',receipt);print(json.dumps(receipt),flush=True)
