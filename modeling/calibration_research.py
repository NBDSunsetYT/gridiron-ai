"""Offline monotone calibration candidates. No service route imports this module.

These methods calibrate archived probabilities; they do not change simulated
games or imply that score accuracy, lineup coverage or uncertainty improved.
"""
import numpy as np

def probabilities(values):
    p=np.asarray(values,dtype=float)
    if p.ndim!=1 or not len(p) or not np.isfinite(p).all() or np.any((p<0)|(p>1)):raise ValueError('Finite probabilities required')
    return p

def sigmoid(x):return 1/(1+np.exp(-np.clip(x,-40,40)))
def logit(p):p=np.clip(probabilities(p),1e-6,1-1e-6);return np.log(p/(1-p))

def fit(kind,p,y):
    p=probabilities(p);y=np.asarray(y,dtype=float)
    if y.shape!=p.shape or not np.isin(y,[0,1]).all() or len(p)<8 or min(sum(y==0),sum(y==1))<2:raise ValueError('Insufficient chronological training outcomes')
    if kind=='temperature':
        temperatures=np.geomspace(.5,4,161);x=logit(p)
        losses=[metrics(sigmoid(x/t),y)['logLoss'] for t in temperatures]
        return {'kind':kind,'temperature':float(temperatures[int(np.argmin(losses))]),'n':len(p)}
    if kind=='platt':
        x=np.column_stack([logit(p),np.ones(len(p))]);beta=np.array([1.,0.]);prior=beta.copy();penalty=np.diag([2.,2.])
        def objective(b):
            q=np.clip(sigmoid(x@b),1e-12,1-1e-12);return -sum(y*np.log(q)+(1-y)*np.log1p(-q))+.5*(b-prior)@penalty@(b-prior)
        for _ in range(50):
            q=sigmoid(x@beta);grad=x.T@(q-y)+penalty@(beta-prior);h=x.T@((q*(1-q))[:,None]*x)+penalty
            step=np.linalg.solve(h,grad);rate=1.
            while rate>1e-6:
                proposal=beta-rate*step;proposal[0]=max(0.,proposal[0])
                if objective(proposal)<=objective(beta):break
                rate*=.5
            if np.linalg.norm(proposal-beta)<1e-8:break
            beta=proposal
        return {'kind':kind,'slope':float(beta[0]),'intercept':float(beta[1]),'ridge':2.,'n':len(p)}
    if kind=='isotonic':
        xs=np.unique(p);blocks=[]
        for value in xs:
            mask=p==value;blocks.append([float(value),float(value),float(sum(y[mask])),int(sum(mask))])
            while len(blocks)>1 and blocks[-2][2]/blocks[-2][3]>blocks[-1][2]/blocks[-1][3]:
                b=blocks.pop();a=blocks.pop();blocks.append([a[0],b[1],a[2]+b[2],a[3]+b[3]])
        knots=[];rates=[]
        for a,b,h,n in blocks:
            knots.append(a);rates.append(h/n)
            if b!=a:knots.append(b);rates.append(h/n)
        return {'kind':kind,'x':knots,'p':rates,'n':len(p)}
    raise ValueError('Unsupported calibration method')

def predict(model,p):
    p=probabilities(p)
    if model['kind']=='temperature':out=sigmoid(logit(p)/model['temperature'])
    elif model['kind']=='platt':out=sigmoid(model['slope']*logit(p)+model['intercept'])
    elif model['kind']=='isotonic':out=np.interp(p,model['x'],model['p'])
    else:raise ValueError('Unsupported calibration artifact')
    return np.clip(out,1e-6,1-1e-6)

def metrics(p,y):
    p=probabilities(p);y=np.asarray(y,dtype=float)
    if p.shape!=y.shape or not np.isin(y,[0,1]).all():raise ValueError('Binary matched outcomes required')
    bins=[]
    for low in np.arange(0,1,.2):
        at=(p>=low)&(p<low+.2+1e-12)
        # Disjoint fixed-width bins; a boundary belongs only to the next bin.
        at=np.minimum(4,np.floor(p*5).astype(int))==int(round(low*5))
        if at.any():bins.append({'n':int(sum(at)),'meanPredicted':float(np.mean(p[at])),'observed':float(np.mean(y[at]))})
    safe=np.clip(p,1e-12,1-1e-12)
    return {'n':len(p),'brier':float(np.mean((p-y)**2)),'logLoss':float(-np.mean(y*np.log(safe)+(1-y)*np.log1p(-safe))), 'ece':sum(b['n']*abs(b['meanPredicted']-b['observed']) for b in bins)/len(p),'bins':bins}

def paired_interval(before,after,seed=1701):
    delta=np.asarray(after)-np.asarray(before)
    if not len(delta):return None
    rng=np.random.default_rng(seed);means=np.mean(delta[rng.integers(0,len(delta),(1000,len(delta)))],axis=1)
    return {'mean':float(np.mean(delta)),'bootstrap95':[float(x) for x in np.quantile(means,[.025,.975])],'unit':'game','negativeIsBetter':True}

def chronological_windows(rows):
    """Whole date cohorts prevent same-day games leaking into their own fit."""
    eligible=[r for r in rows if r.get('phase')=='validation']
    cohorts=sorted({str(r['cohort']) for r in eligible})
    for index,cohort in enumerate(cohorts[1:],1):
        train=sorted([r for r in eligible if str(r['cohort']) in cohorts[:index]],key=lambda r:r['eventStart'])
        test=sorted([r for r in eligible if str(r['cohort'])==cohort],key=lambda r:r['eventStart'])
        if train and test:
            if max(r['eventStart'] for r in train)>=min(r['eventStart'] for r in test):raise ValueError('Chronology violation')
            yield train,test
