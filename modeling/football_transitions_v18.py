"""Source-fitted transition metadata; absence is not an observed zero rate."""
from collections import Counter,defaultdict
from datetime import timedelta
from copy import deepcopy
import hashlib,json
import numpy as np
from sklearn.linear_model import LogisticRegression
from .fit import utc

VERSION='football-transition-metadata-18.0.0'
START_TYPES=('kickoff','post_score','post_turnover','post_punt')
def position_priors(rows):
    games=defaultdict(Counter);positions={}
    for r in rows:
        for role,key in [('receiver','targets'),('runner','carries')]:
            p=r.get(role);position=r.get(role+'Position')
            if p and position:
                positions[p]=position
                if role=='receiver' and r['kind']=='pass' or role=='runner' and r['kind']=='rush':games[(r['game'],r['o'],key)][p]+=1
    by=defaultdict(list)
    for (game,team,key),counts in games.items():
        for p,n in counts.items():by[(key,positions[p])].append(n/sum(counts.values()))
    fitted={}
    for (key,pos),values in by.items():
        mean=float(np.mean(values));var=float(np.var(values));strength=max(0,mean*(1-mean)/var-1) if var else 0
        fitted.setdefault(key,{})[pos]={'meanShare':mean,'priorOpportunities':min(10000,strength),'observations':len(values)}
    return {'positions':positions,'byPosition':fitted,'missingPositionIsUnknown':True}

def allocate_roles(model,counts,role,current,team,history):
    stat='targets' if role=='receivers' else 'carries';prior=model.get('positionPriors',{});positions={**prior.get('positions',{}),**current.get('positions',{})};depth=current.get('depthChart',{}).get(role,[])
    if len(depth)!=len(set(depth)):raise ValueError('Depth chart has duplicate player identity')
    result={}
    for p in set(counts)|set(depth):
        if p in current.get('inactive',[]):continue
        if p not in counts and not current.get('verified'):continue
        n=float(counts.get(p,0));pooled=prior.get('byPosition',{}).get(stat,{}).get(positions.get(p),{})
        weight=(n+pooled.get('priorOpportunities',0)*pooled.get('meanShare',0))/(sum(counts.values())+pooled.get('priorOpportunities',0)) if pooled else n/max(1,sum(counts.values()))
        if weight>0:result[p]=weight
    rank={p:i for i,p in enumerate(depth)};cap=6 if role=='receivers' else 4
    ordered=sorted(result,key=lambda p:(rank.get(p,len(depth)),-result[p],p))[:cap]
    return {p:result[p] for p in ordered}

def fit_transitions(rows,cutoff,external=None):
    from .simulator import is_late
    if any(utc(r['at'])>=utc(cutoff) for r in rows):raise ValueError('Every transition fit observation must precede cutoff')
    if external and (external.get('cutoff')!=cutoff or any(utc(r['at'])>=utc(cutoff) for r in external.get('rows',[]))):raise ValueError('External transition evidence violates fitting cutoff')
    groups={kind:defaultdict(list) for kind in START_TYPES};seen=set();unclassified=0
    for r in rows:
        if 'down' not in r:continue
        key=(r['game'],r['o'],r.get('drive'))
        if key in seen:continue
        seen.add(key);cause=r.get('startCause')
        if cause in groups:groups[cause][r['o']].append(r['field'])
        else:unclassified+=1
    for r in (external or {}).get('rows',[]):
        if r['kind']=='drive_start' and r.get('cause') in groups:
            groups[r['cause']][r['team']].append(r['field'])
    conversions=[r for r in rows if r['kind'] in ('extra_point','two_point')]
    conversions.extend(r for r in (external or {}).get('rows',[]) if r['kind'] in ('extra_point','two_point'))
    # External contextual rows replace uncontextualized copies of those tries.
    contextual=[r for r in conversions if r.get('script') is not None and r.get('clock') is not None]
    usable=contextual if contextual else conversions;labels=np.array([r['kind']=='two_point' for r in usable],int)
    decision={'n':len(labels),'twoPoint':int(labels.sum()),'contextual':bool(contextual),'coefficients':None,'intercept':None}
    if contextual and len(set(labels))==2:
        x=np.array([[r['script']/21,float(r['clock']<=120),r['clock']/3600] for r in contextual]);m=LogisticRegression(C=1.,max_iter=500).fit(x,labels);decision.update(coefficients=m.coef_[0].tolist(),intercept=float(m.intercept_[0]))
    return_events={}
    for kind in ('interception','fumble','punt','kickoff'):
        cohort=[r for r in (external or {}).get('rows',[]) if r['kind']==kind];rs=[r for r in cohort if r.get('returnTouchdown') is not None];complete=bool(rs) and len(rs)==len(cohort)
        return_events[kind]={'n':len(rs),'touchdowns':sum(bool(r['returnTouchdown']) for r in rs),'unverifiedEvents':len(cohort)-len(rs),'rate':sum(bool(r['returnTouchdown']) for r in rs)/len(rs) if complete else None,'returnYards':[r['returnYards'] for r in rs if r.get('returnYards') is not None]}
    clock={}
    for kind in ('pass','rush','sack','spike'):
        rs=[r for r in rows if r['kind']==kind and r.get('elapsed',0)>0];fast=[r['elapsed'] for r in rs if is_late(r['clock'],True) and r.get('script',0)<0];normal=[r['elapsed'] for r in rs if not is_late(r['clock'],True)]
        clock[kind]={'twoMinuteTempoMultiplier':float(np.mean(fast)/np.mean(normal)) if fast and normal else None,'lateSamples':len(fast),'ordinarySamples':len(normal)}
    bounds={}
    for kind in ('pass','rush','sack'):
        rs=[r for r in rows if r['kind']==kind and r.get('outOfBounds') is not None];bounds[kind]={'n':len(rs),'outOfBounds':sum(bool(r['outOfBounds']) for r in rs),'rate':sum(bool(r['outOfBounds']) for r in rs)/len(rs) if rs else None}
    late_pass=[r for r in rows if r['kind'] in ('pass','spike') and is_late(r['clock'],True)];known=[r for r in late_pass if r['kind']=='spike' or r.get('isSpike') is not None];spikes=sum(r['kind']=='spike' for r in known)
    result={'version':VERSION,'starts':{k:dict(v) for k,v in groups.items()},'unclassifiedStarts':unclassified,'twoPointDecision':decision,'returnTouchdowns':return_events,'clock':clock,'outOfBounds':bounds,'spikeDecision':{'n':len(known),'spikes':spikes,'rate':spikes/len(known) if known and len(known)==len(late_pass) else None},'sourceVersion':(external or {}).get('sourceVersion'),'missingIsZero':False}
    result['sha256']=hashlib.sha256(json.dumps(result,sort_keys=True,separators=(',',':')).encode()).hexdigest();return result

def two_point_probability(model,diff,clock):
    d=model['transitions']['twoPointDecision']
    if d['n']<=0:raise ValueError('No observed conversion decisions')
    if d['coefficients'] is None:return np.full(np.broadcast(diff,clock).shape,d['twoPoint']/d['n'])
    x=np.stack(np.broadcast_arrays(np.asarray(diff)/21,np.asarray(clock)<=120,np.asarray(clock)/3600),axis=-1).astype(float);eta=x@np.array(d['coefficients'])+d['intercept'];return 1/(1+np.exp(-np.clip(eta,-700,700)))

def starts(model,team,cause):
    if cause not in START_TYPES:raise ValueError('Explicit possession restart cause required')
    pool=model.get('transitions',{}).get('starts',{}).get(cause,{}).get(team,[])
    # Compatibility is explicit, never described as verified kickoff evidence.
    return pool or model['starts'][team]

def migrate(model,rows,external=None):
    if model.get('version') not in ('football-possession-hurdle-candidate-15.1.0','football-possession-candidate-15.0.0'):raise ValueError('Only fitted v15 football artifacts migrate without refitting')
    migrated=deepcopy(model);migrated['version']='football-market-candidate-18.0.0';migrated['transitions']=fit_transitions(rows,model['fittingCutoff'],external);migrated['positionPriors']=position_priors(rows)
    for kind in migrated['clock']:migrated['clock'][kind]=[r['elapsed'] for r in rows if r['kind']==kind and r.get('elapsed',0)>0]
    migrated['clock']['spike']=[r['elapsed'] for r in rows if r['kind']=='spike' and r.get('elapsed',0)>0];migrated['stoppedClocks']={'spike':migrated['clock']['spike']};migrated['liveClocks']=[r['elapsed'] for r in rows if r['kind']=='pass' and not r.get('complete') and not r.get('int') and r.get('elapsed',0)>0];migrated['kindOrder']=['pass','rush','punt','field_goal','kneel','penalty','spike']
    dates=[r['at'] for r in rows]+[r['at'] for r in (external or {}).get('rows',[])];migrated['asOf']=max(utc(model['asOf']),max(utc(v) for v in dates)+timedelta(microseconds=1)).isoformat()
    migrated['migration']={'fromVersion':model['version'],'fromSHA256':model['sha256'],'coefficientsRefit':False,'missingTypedStarts':'Explicit legacy pooled-start compatibility; not verified kickoff data'};migrated.pop('sha256',None);migrated['sha256']=hashlib.sha256(json.dumps(migrated,sort_keys=True,separators=(',',':')).encode()).hexdigest();return migrated
