"""Original GAFIE conditional-transition research candidate.

Learns regularized multiclass play selection from real state/identity features,
then draws one *joint historical play event* from verified conditional support.
The existing sport-specific state machine applies that event to possession,
clock, down/distance, score and every participant. No random score generator or
independent player-stat sampler exists in this model. Safe JSON, never pickle.

This is experimental until full-game chronological distribution validation;
play-class accuracy alone cannot promote it. No borrowed implementation code.
"""
from collections import Counter,defaultdict,OrderedDict
from datetime import datetime,timezone
import hashlib,json,math
import numpy as np
from sklearn.linear_model import LogisticRegression
from .simulator import Evidence,simulate,zone,distance_bucket,script_bucket
from .cfb_simulator import CFBEvidence,simulate_cfb

VERSION='gafie-conditional-transition-14.0.0'
NUMERIC=['down1','down2','down3','down4','distance10','field100','halfClock1800','score21','trailingLate','leadingLate','distanceByDown','redZone']
def vector(team,defense,down,field,distance,diff,clock,teams):
    remaining=clock-1800 if clock>1800 else clock
    late=float(remaining<=120)
    return np.asarray([float(down==i) for i in (1,2,3,4)]+[distance/10,field/100,remaining/1800,diff/21,float(diff<0)*late,float(diff>0)*late,distance*down/40,float(field<=20)]+[float(team==t) for t in teams]+[float(defense==t) for t in teams],dtype=np.float64)
def row_vector(row,teams):return vector(row['o'],row['d'],row['down'],row['field'],row['distance'],row['script'],row['clock'],teams)
def scores(y,p):
    matrix=np.zeros_like(p);matrix[np.arange(len(y)),y]=1
    return {'logLoss':float(-np.log(np.maximum(1e-15,p[np.arange(len(y)),y])).mean()),'multiclassBrier':float(((p-matrix)**2).sum(axis=1).mean()),'n':len(y)}
def fit_gafie(model):
    sport='CFB' if model.get('sport')=='CFB' else 'NFL'
    rows=[r for r in model['rows'] if r['kind'] not in ('extra_point','two_point')]
    games=sorted({r['game'] for r in rows},key=lambda g:min(r['at'] for r in rows if r['game']==g))
    if len(games)<12 or len(rows)<800:raise ValueError('GAFIE needs at least twelve actual historical games and 800 supported plays')
    train_games=set(games[:int(len(games)*.65)]);test_games=set(games[int(len(games)*.65):]);train=[r for r in rows if r['game'] in train_games];test=[r for r in rows if r['game'] in test_games]
    if max(r['at'] for r in train)>=min(r['at'] for r in test):raise ValueError('Chronological game-block split overlaps; no future-play training allowed')
    teams=sorted({r[k] for r in train for k in ('o','d')});classes=sorted({r['kind'] for r in train});index={k:i for i,k in enumerate(classes)}
    if len(classes)<2 or any(r['kind'] not in index for r in test):raise ValueError('Unseen play types require more historical training coverage')
    x=np.stack([row_vector(r,teams) for r in train]);y=np.asarray([index[r['kind']] for r in train]);xt=np.stack([row_vector(r,teams) for r in test]);yt=np.asarray([index[r['kind']] for r in test]);fitted=LogisticRegression(C=1.,max_iter=600,solver='lbfgs').fit(x,y)
    if len(classes)==2:coefficients=np.vstack([np.zeros(x.shape[1]),fitted.coef_[0]]);intercepts=np.asarray([0.,fitted.intercept_[0]])
    else:coefficients=fitted.coef_;intercepts=fitted.intercept_
    # State-aware, same-team empirical baseline, fitted on training games only.
    counts=defaultdict(Counter)
    for r in train:
        key=(r['o'],r['down'],zone(r['field']),distance_bucket(r['distance']),script_bucket(r['script']),r['clock']<=120 or 1800<r['clock']<=1920)
        counts[key][r['kind']]+=1;counts[(r['o'],r['down'])][r['kind']]+=1
    prior=Counter(r['kind'] for r in train);baseline=[]
    for r in test:
        key=(r['o'],r['down'],zone(r['field']),distance_bucket(r['distance']),script_bucket(r['script']),r['clock']<=120 or 1800<r['clock']<=1920);c=counts.get(key);c=c if c and sum(c.values())>=3 else counts.get((r['o'],r['down']),prior)
        baseline.append([(c.get(k,0)+.5)/(sum(c.values())+.5*len(classes)) for k in classes])
    actual=fitted.predict_proba(xt);candidate=scores(yt,actual);reference=scores(yt,np.asarray(baseline));created=datetime.now(timezone.utc).isoformat()
    artifact={'version':VERSION,'sport':sport,'baseModelVersion':model['version'],'createdAt':created,'dataCutoff':model['asOf'],'inputVersion':model['sha256'],'features':NUMERIC+['offense:'+t for t in teams]+['defense:'+t for t in teams],'teams':teams,'classes':classes,'coefficients':coefficients.tolist(),'intercepts':intercepts.tolist(),'trainingGames':sorted(train_games),'holdoutGames':sorted(test_games),'trainingPlays':len(train),'holdoutPlays':len(test),'validation':{'chronological':True,'candidate':candidate,'stateAwareHistoricalBaseline':reference,'scope':'Held-out play selection only; full-game score/player calibration and personnel transport remain unvalidated.'},'productionEligible':False,'limitations':['Historical personnel and joint outcome resampling do not independently estimate current depth-chart or injury effects.','Team identity coefficients are regularized associations, not identified causal offense/defense strengths.','Outcome selection is restricted to observed same-team conditional support; unsupported play types are not invented.','No validated weather, tracking/coverage, route or injury-redistribution multiplier is manufactured.','The full-game candidate cannot be promoted from play-level metrics alone.']}
    artifact['artifactId']=hashlib.sha256(json.dumps(artifact,sort_keys=True).encode()).hexdigest();return artifact

class TransitionMixin:
    def __init__(self,model,*args,**kwargs):
        super().__init__(model,*args,**kwargs)
        a=model.get('gafie');sport='CFB' if model.get('sport')=='CFB' else 'NFL'
        if not a or a.get('version')!=VERSION or a.get('sport')!=sport or a.get('inputVersion')!=model['sha256']:raise ValueError('A separately fitted, exact-input GAFIE artifact is required')
        self.gafie=a;self.coefficients=np.asarray(a['coefficients']);self.intercepts=np.asarray(a['intercepts']);self.transition_cache=OrderedDict();self.type_pools={}
        if self.coefficients.shape!=(len(a['classes']),len(a['features'])) or not np.isfinite(self.coefficients).all() or not np.isfinite(self.intercepts).all():raise ValueError('Invalid GAFIE coefficient shape or numerical values')
    def sample(self,rng,team,defense,down,field,distance,diff,clock):
        keys=((team,defense,down,zone(field),distance_bucket(distance),script_bucket(diff),clock<=120),(team,down,zone(field),distance_bucket(distance),script_bucket(diff),clock<=120),(team,down,zone(field),distance_bucket(distance)),(team,down))
        selected=next(((depth,self.pools[k]) for depth,k in enumerate(keys) if len(self.pools.get(k,[]))>=3),None)
        if selected is None:raise ValueError('No observed joint-event support for this GAFIE state')
        depth,pool=selected;self.backoff[depth]+=1;identity=(id(pool),team,defense,down,field,distance,diff,clock)
        cached=self.transition_cache.get(identity)
        if cached is None:
            by_type=self.type_pools.get(id(pool))
            if by_type is None:
                by_type={kind:[r for r in pool if r['kind']==kind] for kind in self.gafie['classes']};self.type_pools[id(pool)]=by_type
            logits=self.coefficients@vector(team,defense,down,field,distance,diff,clock,self.gafie['teams'])+self.intercepts;weights=np.exp(logits-logits.max());support=[(kind,float(weights[i]),by_type[kind]) for i,kind in enumerate(self.gafie['classes']) if by_type[kind]]
            total=sum(w for _,w,_ in support)
            if total<=0 or not math.isfinite(total):raise ValueError('Unstable learned play-call probabilities')
            cumulative=0.;cdf=[]
            for kind,w,rows in support:cumulative+=w/total;cdf.append((cumulative,rows))
            cached=cdf
            if len(self.transition_cache)>=4096:self.transition_cache.popitem(last=False)
            self.transition_cache[identity]=cached
        u=rng.random()
        for cumulative,rows in cached:
            if u<cumulative:return self.draw(rng,rows)
        return self.draw(rng,cached[-1][1])

class GafieNFL(TransitionMixin,Evidence):pass
class GafieCFB(TransitionMixin,CFBEvidence):pass

def simulate_gafie(model,home,away,simulations=10000,seed=14013,event_start=None,representative_games=1):
    if not model.get('gafie'):raise ValueError('Fit an original GAFIE candidate from the verified historical artifact first')
    sport='CFB' if model.get('sport')=='CFB' else 'NFL';engine=simulate_cfb if sport=='CFB' else simulate
    result=engine(model,home,away,simulations,seed,event_start,representative_games=representative_games,_evidence_factory=GafieCFB if sport=='CFB' else GafieNFL)
    base=result['modelVersion'];result.update(modelVersion=('cfb-' if sport=='CFB' else '')+VERSION,baseModelVersion=base,modelStatus='experimental_unpromoted',gafieArtifactId=model['gafie']['artifactId'],gafieValidation=model['gafie']['validation'])
    result['runManifest']['modelVersion']=result['modelVersion'];result['runManifest']['configuration']['transitionModelVersion']=VERSION;result['limitations']+=model['gafie']['limitations'];return result
