"""Evaluate frozen pre-July projection models on new validation IDs.
This is an unchanged-model baseline, not another calibration search.
"""
import sys,pickle,json,gzip,time,resource,os
from pathlib import Path
from collections import defaultdict
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from modeling.structural_v18.data import build_dataset
from modeling.structural_v18.models import FAMILIES,OPPORTUNITY,error_metrics,cluster_delta
from modeling.iterative_learning import freeze_json
from modeling.reconstruction_v19.runtime import local_only
OUT=ROOT/'artifacts/parallel-v19'

def main():
    local_only()
    if (OUT/'projection-results.json').exists():
        print(json.dumps({'status':'immutable_projection_campaign_complete','newTrainingRuns':0}));return
    resource.setrlimit(resource.RLIMIT_CPU,(180,182));start=time.process_time();p=json.load((OUT/'protocol.json').open());report={}
    for sport in ['NFL','CFB','NBA']:
        end=max(g['at'] for g in p['selection'][sport])[:10]+'T23:59:59+00:00';rows,games=build_dataset(sport,end);selected={g['id']:g for g in p['selection'][sport]};valid=[r for r in rows if r['gameId'] in selected];models=pickle.load((ROOT/'artifacts/structural-v18'/(sport+'-projection-models.pickle')).open('rb'));groups=defaultdict(list)
        for r in valid:groups[(r['player']=='__team__',r['stat'])].append(r)
        predicted={};out=[];summary={}
        for key in sorted(groups,key=lambda k:(k[1] not in ('minutes','passingAttempts','targets','carries'),k)):
            rs=groups[key];ident=lambda r:(r['gameId'],r['team'],r['player']);summary[str(key)]={}
            for family in FAMILIES:
                m=models[(key,family)];op=None
                if family=='hybrid' and getattr(m,'rate',None) is not None:op=np.array([predicted[((key[0],OPPORTUNITY[key[1]]),'ridge')][ident(r)] for r in rs])
                values=m.predict(rs,op);predicted[(key,family)]={ident(r):float(v) for r,v in zip(rs,values)};ys=[r['y'] for r in rs];baseline=[r['baseline'] for r in rs]
                summary[str(key)][family]={**error_metrics(ys,values),'games':len({r['gameId'] for r in rs}),'players':len({r['player'] for r in rs}),'pairedVsRolling':cluster_delta(rs,baseline,values),'windows':{str(i):error_metrics([r['y'] for r in rs if selected[r['gameId']]['cohort']==i],[v for r,v in zip(rs,values) if selected[r['gameId']]['cohort']==i]) for i in range(3)}}
            for r in rs:out.append({'gameId':r['gameId'],'team':r['team'],'player':r['player'],'stat':r['stat'],'featureCutoff':r['featureCutoff'],'predictions':{f:predicted[(key,f)][ident(r)] for f in FAMILIES}})
        freeze_json(OUT/'projections'/(sport+'.json.gz'),{'sport':sport,'trainingCutoff':'2025-07-01','frozenModelsReused':True,'rows':out});report[sport]={'games':len({r['gameId'] for r in valid}),'players':len({r['player'] for r in valid if r['player']!='__team__'}),'rows':len(valid),'groups':summary};print(json.dumps({'sport':sport,'games':report[sport]['games'],'cpuSeconds':time.process_time()-start}),flush=True)
    freeze_json(OUT/'projection-results.json',{'leagues':report,'cpuSeconds':time.process_time()-start,'newTrainingRuns':0,'newCalibrators':0,'peakRssKiB':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss})
if __name__=='__main__':main()
