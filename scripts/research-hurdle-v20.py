"""One preregistered structural challenger, three independent sport fits.
Window zero is development; windows one through three are validation, never a
sealed final test. Predictions are frozen before any current-window grading.
"""
import sys,os,json,gzip,time,pickle
from pathlib import Path
from collections import defaultdict
from datetime import timedelta
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from modeling.overnight_v20.state import Campaign,atomic,read,process_identity,digest
from modeling.overnight_v20.sources import protocol
from modeling.overnight_v20.cohort import training_rows,point_grade,official_box,lineup
from modeling.overnight_v20 import data
from modeling.reconstruction_v19.evidence import aware
from modeling.iterative_learning import freeze_json
from modeling.opportunity_hurdle_v20 import HurdleProjection,VERSION
from modeling.structural_v18.models import error_metrics
OUT=ROOT/'artifacts/overnight-v20';folder=OUT/'hurdle';folder.mkdir(exist_ok=True);preregister=folder/'protocol.json';definition={'version':VERSION,'developmentWindows':[0],'validationWindows':[1,2,3],'primary':{'NFL':'passingYards','CFB':'passingYards','NBA':'rebounds'},'hypothesis':'Explicit zero-opportunity probability and conditional volume/efficiency may reduce dense-regression workload inflation for intermittent players.','hyperparameters':{'volumeRidge':100,'rateRidge':100,'presenceC':.05,'minimumRows':100,'minimumPositiveRows':40},'reservedFinalOpened':False,'productionPromotion':False,'maximumCpuSeconds':600,'sourceSha256':__import__('hashlib').sha256((ROOT/'modeling/opportunity_hurdle_v20.py').read_bytes()).hexdigest()}
if preregister.exists() and read(preregister)!=definition:raise RuntimeError('Candidate definition changed; preserve and register another ID')
if not preregister.exists():freeze_json(preregister,definition)
if '--register-only' in sys.argv:print(json.dumps(definition,indent=2));sys.exit(0)
campaign=Campaign(OUT/'runtime')
with campaign.lease():
    campaign.begin();allowed,why=campaign.may_start(600)
    if not allowed:campaign.end(why);raise RuntimeError(why)
    import resource,signal
    resource.setrlimit(resource.RLIMIT_CPU,(int(time.process_time())+600,int(time.process_time())+605));signal.alarm(1200);campaign.claim('hurdle-v20',process_identity(os.getpid()),600,definition);before=time.process_time();receipt={'status':'failed'}
    try:
        for sport in ['NFL','CFB','NBA']:
            packets=data.packets(sport);evidence=json.loads(gzip.decompress((OUT/'evidence'/(sport+'-aligned-v3.json.gz')).read_bytes()));history=defaultdict(list)
            for g in packets:
                for t in [g['home'],g['away']]:history[t].append(g)
            for cohort in range(4):
                dest=folder/(sport+'-'+str(cohort));dest.mkdir(exist_ok=True);games=[g for g in protocol()['selection'][sport] if g['cohort']==cohort]
                if not games:continue
                if (dest/'grades.json.gz').exists():continue
                cutoff=(min(aware(g['at']) for g in games)-timedelta(hours=6)).isoformat();rows,ids=training_rows(packets,cutoff);grouped=defaultdict(list)
                for r in rows:
                    if r['player']!='__team__':grouped[r['stat']].append(r)
                fits={};unsupported={}
                for stat,rs in grouped.items():
                    try:fits[stat]=HurdleProjection().fit(rs)
                    except ValueError as e:unsupported[stat]=str(e)
                predicted=[]
                for g in games:
                    lf=lineup(g,evidence)
                    for team in [g['home'],g['away']]:
                        rs=data.features_for(g,team,history,sport);by=defaultdict(list)
                        for r in rs:
                            if r['player']!='__team__' and not r['player'].split(':')[-1].startswith('-'):by[r['stat']].append(r)
                        for stat,items in by.items():
                            if stat not in fits:continue
                            values=fits[stat].predict(items)
                            for r,v in zip(items,values):
                                out=r['player'] in lf[team]['inactive'];predicted.append({k:r[k] for k in ['gameId','team','player','stat','role','season','featureCutoff']}|{'predictions':{'rolling5':0. if out else r['baseline'],'hurdle':0. if out else float(v)},'knownOutAtCutoff':out,'injuryEvidence':'partial' if lf[team]['source'] else 'unavailable','featureSha256':digest(r['x']),'cohort':cohort})
                if not (dest/'forecasts.json.gz').exists():
                    freeze_json(dest/'forecasts.json.gz',{'rows':predicted,'trainingIds':sorted(ids),'training':{k:m.training for k,m in fits.items()},'unsupported':unsupported,'phase':'development' if cohort==0 else 'validation','reservedFinalOpened':False,'historicalPublicationComplete':False})
                    with (dest/'models.pickle').open('xb') as f:pickle.dump(fits,f)
                else:predicted=json.loads(gzip.decompress((dest/'forecasts.json.gz').read_bytes()))['rows']
                boxes={g['id']:official_box(g,packets) for g in games};grades=point_grade(predicted,boxes,sport);freeze_json(dest/'grades.json.gz',grades);print(json.dumps({'sport':sport,'window':cohort,'rows':len(grades),'cpuSeconds':time.process_time()-before}),flush=True)
        receipt={'status':'completed','cpuSeconds':time.process_time()-before,'candidate':VERSION,'reservedFinalOpened':False,'productionWrites':0};freeze_json(folder/'receipt.json',receipt)
    finally:
        receipt.setdefault('cpuSeconds',time.process_time()-before);campaign.finish('hurdle-v20',receipt);campaign.end('hurdle_validation_checkpoint')
