"""Post-grade algebraic error attribution. Never feeds outcomes into a fit."""
import sys,json,gzip,itertools,math
from pathlib import Path
from collections import defaultdict
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from modeling.integration_v22.io import OUT
from modeling.integration_v22.datasets import cfb_packets,all_packets
from modeling.integration_v22.metrics import paired
from modeling.overnight_v20 import data
from modeling.overnight_v20.state import atomic,read
from modeling.integration_v22.runtime import job
def unpack(p):return json.loads(gzip.decompress(p.read_bytes()))
def attribute(predicted,actual):
    """Shapley decomposition of product error, not causal attribution."""
    if len(predicted)!=len(actual):raise ValueError('Matching factor dimensions required')
    n=len(actual);out=np.zeros(n)
    for ordering in itertools.permutations(range(n)):
        v=np.asarray(actual,float).copy();before=float(np.prod(v))
        for i in ordering:
            v[i]=predicted[i];after=float(np.prod(v));out[i]+=after-before;before=after
    out/=math.factorial(n)
    if abs(out.sum()-(np.prod(predicted)-np.prod(actual)))>1e-6:raise AssertionError('Error attribution does not reconcile')
    return out.tolist()
def run():
    packets,_=cfb_packets();by={g['id']:g for g in packets};out=[];skips=defaultdict(int)
    for p in (OUT/'components/CFB').glob('*/grades.json.gz'):
        for r in unpack(p):
            f=r.get('factors')
            if r['stat']!='passingYards' or not f:continue
            n=r['actualAttempts'];c=r['actualCompletions'];team=by[r['gameId']]['teams'][r['team']]['totals']['passingAttempts']
            if min(n,c,team)<=0:skips['zero_opportunity_or_completion_efficiency_not_identified']+=1;continue
            pred=[f[k] for k in ['teamAttempts','opportunityShare','completionRate','yardsPerCompletion']];act=[team,n/team,c/n,r['actual']/c];values=attribute(pred,act);out.append({'eventId':r['gameId'],'team':r['team'],'player':r['player'],'signedError':r['predictions']['chain']-r['actual'],'contributions':dict(zip(['teamPassingVolume','QBOpportunityShare','completionEfficiency','yardsPerCompletion'],values)),'interpretation':'Algebraic accounting; no causal injury attribution or postgame model tuning'})
    result={'eligiblePlayerGameAttributions':len(out),'gameCount':len({r['eventId'] for r in out}),'undefinedFactorRows':dict(skips),'meanSignedContribution':{k:float(np.mean([r['contributions'][k] for r in out])) for k in ['teamPassingVolume','QBOpportunityShare','completionEfficiency','yardsPerCompletion']},'meanAbsoluteContribution':{k:float(np.mean([abs(r['contributions'][k]) for r in out])) for k in ['teamPassingVolume','QBOpportunityShare','completionEfficiency','yardsPerCompletion']},'individualExamples':sorted(out,key=lambda r:abs(r['signedError']),reverse=True)[:12],'notCausal':True,'changesToForecasts':0};atomic(OUT/'diagnostics/cfb-factor-errors.json',result)
    all_data,_,_=all_packets();protocol=read(OUT/'protocol.json');slices={};missing=[]
    for sport in ['NFL','CFB']:
        hist=defaultdict(list);opportunities={};grades=[]
        for g in all_data[sport]:
            for t in [g['home'],g['away']]:hist[t].append(g)
        for ws in protocol['selection'][sport]:
            for g in ws:
                count=0
                for t in [g['home'],g['away']]:
                    for r in data.features_for(g,t,hist,sport):
                        if r['stat']=='passingAttempts' and r['player']!='__team__':opportunities[(g['id'],t,r['player'])]=r['baseline'];count+=1
                if count==0:missing.append({'eventId':g['id'],'sport':sport,'reason':'No prior-known passing player frame with three eligible earlier own/opponent appearances; missing history is not confirmed inactivity'})
        for p in (OUT/'components'/sport).glob('*/grades.json.gz'):grades.extend(r for r in unpack(p) if r['stat']=='passingYards')
        slices[sport]={str(threshold):paired([r for r in grades if opportunities.get((r['gameId'],r['team'],r['player']),0)>=threshold],'hurdle' if sport=='NFL' else 'chain','production_source_replay' if sport=='NFL' else 'hurdle') for threshold in [10,25]}
    atomic(OUT/'diagnostics/prior-attempt-volume-slices.json',{'thresholdsArePriorAttemptsPerGame':[10,25],'slices':slices,'missingFrames':missing,'postgradeDescriptiveAnalysis':True,'notUsedForModelSelection':True});return result
if __name__=='__main__':
    import hashlib
    path=OUT/'specs/diagnostics.json'
    if '--register' in sys.argv:
        if path.exists():raise ValueError('Diagnostics already registered')
        files=[Path(__file__),ROOT/'modeling/integration_v22/datasets.py'];atomic(path,{'numericCode':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files},'postgradeOnly':True,'modelSelectionAllowed':False,'slices':'Prior QB ATT per game >=10 and >=25; not postgame starter inference'});print('Registered algebraic diagnostics')
    else:print(json.dumps(job('diagnostics',run,cpu=120,wall=360),indent=2))
