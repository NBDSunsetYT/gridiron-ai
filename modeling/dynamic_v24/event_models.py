"""ABC ablations on identical event rows. No fixed momentum multipliers."""
from collections import Counter,defaultdict
import numpy as np
from sklearn.feature_extraction import DictVectorizer
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline

VARIANTS=('A','B','C','B_momentum','B_fatigue')
def features(row,variant):
    base=dict(row['base']);dyn=row.get('dynamic',{})
    if variant=='A':return {k:v for k,v in base.items() if k in ('team','opponent','actor','shotValue','shotX','shotY','shotLocationMissing','down','distance','field','remaining','period','score_diff')}
    if variant in ('C','B_momentum'):base.update({k:v for k,v in dyn.items() if not k.startswith('fatigue_')})
    if variant in ('C','B_fatigue'):base.update({k:v for k,v in dyn.items() if k.startswith('fatigue_')})
    return base

class EventModel:
    def __init__(self,variant):
        if variant not in VARIANTS:raise ValueError('Unregistered event variant')
        self.variant=variant
    def fit(self,rows):
        if len(rows)<200:raise ValueError('Two hundred training events required')
        self.classes=sorted({r['y'] for r in rows},key=str);self.binary=len(self.classes)==2
        if len(self.classes)<2:raise ValueError('No class variation')
        self.model=make_pipeline(DictVectorizer(sparse=True),StandardScaler(with_mean=False),LogisticRegression(C=.03,max_iter=2000,solver='lbfgs',random_state=24024));self.model.fit([features(r,self.variant) for r in rows],[r['y'] for r in rows]);self.classes=list(self.model[-1].classes_);self.converged=bool(np.max(self.model[-1].n_iter_)<self.model[-1].max_iter)
        if not self.converged:raise RuntimeError('Event model failed the numerical convergence gate')
        return self
    def predict(self,rows):return self.model.predict_proba([features(r,self.variant) for r in rows])

def categorical_metrics(rows,p,classes):
    labels={v:i for i,v in enumerate(classes)};y=np.array([labels[r['y']] for r in rows]);p=np.clip(p,1e-9,1);p/=p.sum(axis=1,keepdims=True);truth=np.eye(len(classes))[y];loss=-np.log(p[np.arange(len(y)),y]);brier=np.sum((p-truth)**2,axis=1)/(2 if len(classes)==2 else 1);confidence=p.max(axis=1);correct=(p.argmax(axis=1)==y).astype(float);bins=np.digitize(confidence,np.linspace(0,1,6)[1:-1]);ece=sum(np.mean(bins==b)*abs(float(np.mean(confidence[bins==b])-np.mean(correct[bins==b]))) for b in range(5) if np.any(bins==b))
    return {'events':len(rows),'games':len({r['gameId'] for r in rows}),'logLoss':float(loss.mean()),'brier':float(brier.mean()),'accuracy':float(correct.mean()),'ECE':float(ece),'losses':loss,'brierRows':brier,'notPregameForecastAccuracy':True}

def paired_losses(rows,baseline,candidate,seed=24024,alpha=.05/6):
    groups=defaultdict(list)
    for i,r in enumerate(rows):groups[r['gameId']].append(i)
    delta=np.array([float(np.mean(candidate[ix]-baseline[ix])) for ix in groups.values()]);rng=np.random.default_rng(seed);draw=np.mean(delta[rng.integers(0,len(delta),size=(3000,len(delta)))],axis=1)
    return {'games':len(groups),'meanGameDelta':float(delta.mean()),'CI95':np.quantile(draw,[.025,.975]).tolist(),'familywiseCI':np.quantile(draw,[alpha/2,1-alpha/2]).tolist(),'alpha':alpha,'negativeFavorsCandidate':True,'cluster':'game'}

class EmpiricalReference:
    """Prior-only empirical A reference, never current final-game rates.

    V23 itself has no next-event forecast API and needs final-conditioned
    mechanics inputs. This reference preserves its empirical context policy;
    it is explicitly not a claimed full-game production-champion forecast.
    """
    def fit(self,rows):
        self.classes=sorted({r['y'] for r in rows},key=str);self.global_counts=Counter(r['y'] for r in rows);self.groups=defaultdict(Counter)
        for r in rows:self.groups[self.key(r)].update([r['y']])
        return self
    def key(self,r):
        b=r['base'];return (b['team'],b.get('actor',''),int(b.get('shotValue',0)),int(b.get('down',0)),int(b.get('field',50)//20),int(b.get('distance',10)//5),bool(b.get('remaining',3600)<120))
    def predict(self,rows):
        g=np.array([self.global_counts[c] for c in self.classes],float);g/=g.sum();out=[]
        for r in rows:
            counts=self.groups[self.key(r)];n=sum(counts.values());out.append([(counts[c]+10*g[i])/(n+10) for i,c in enumerate(self.classes)])
        return np.array(out)

class V23PlayReference:
    """Actual unchanged V23 candidate pool, fitted on earlier games only."""
    def fit(self,rows):
        self.rows=rows;self.templates=[r['template'] for r in rows];self.kernels={};self.classes=sorted({r['y'] for r in rows});return self
    def predict(self,rows):
        from ..fullgame_v23.football import PlayKernel
        out=[]
        for r in rows:
            b=r['base'];team=b['team'];other=b['opponent'];pair=(team,other)
            if pair not in self.kernels:self.kernels[pair]=PlayKernel(r['sport'],pair,[t for t in self.templates if t['o'] in pair],{})
            kernel=self.kernels[pair];q=int(b['period']);c=float(r['clock']);down=int(b['down']);field=float(b['field']);distance=float(b['distance']);diff=b['score_diff'];hurry=q in (2,4) and c<=120;key=(team,down,field,distance,hurry,int(np.sign(diff)),False,q in (2,4),())
            kernel.select(np.random.default_rng(24024),team,down,field,c,diff,period=q,distance=distance);pool=kernel.cache[key];counts=Counter('pass' if t['kind']=='sack' else 'rush' if t['kind']=='kneel' else t['kind'] for t in pool);out.append([counts[c]/len(pool) for c in self.classes])
        return np.array(out)
