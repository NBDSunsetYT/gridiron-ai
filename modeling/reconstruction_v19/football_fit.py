"""Separately estimated NFL/CFB recency, contextual tempo and latent efficiency.
No market prices, validation outcomes or post-hoc probability calibration enter.
"""
from collections import defaultdict,Counter
import copy,hashlib,json
import numpy as np
from scipy.sparse import csr_matrix,hstack
from scipy.optimize import minimize_scalar
from scipy.special import gammaln,expit,logit
from sklearn.linear_model import LogisticRegression,Ridge
from .. import football_v15 as base
from ..iterative_learning import digest
from .evidence import aware
VERSION='football-contextual-team-eb-19.0.0'
CLOCK_KINDS=(*base.KINDS,'sack')

def component(rows,labels,teams,cutoff,participants=None,regression=False,field_transform=None):
    x=base.numeric(*[np.array([r[k] for r in rows]) for k in ('down','distance','field','clock','script','home')]);x[:,5]=np.log1p(100*x[:,5])/np.log(101) if field_transform=='log' else x[:,5]
    ti={t:i for i,t in enumerate(teams)};pi={p:i for i,p in enumerate(sorted(set(participants or [])))};ids=[];cols=[]
    for i,r in enumerate(rows):
        ids.extend((i,i));cols.extend((ti[r['o']],len(teams)+ti[r['d']]))
        if participants is not None and participants[i]:ids.append(i);cols.append(2*len(teams)+pi[participants[i]])
    one=csr_matrix((np.ones(len(ids)),(ids,cols)),shape=(len(rows),2*len(teams)+len(pi)));design=hstack((csr_matrix(x),one),format='csr')
    ages=np.array([(aware(cutoff)-aware(r['at'])).total_seconds()/86400 for r in rows]);weights=np.exp2(-ages/180.);weights*=len(weights)/weights.sum()
    fitted=(Ridge(alpha=100.,solver='lsqr') if regression else LogisticRegression(C=1.,max_iter=400,solver='lbfgs')).fit(design,labels,sample_weight=weights)
    co=np.atleast_2d(fitted.coef_);inter=np.atleast_1d(fitted.intercept_);classes=None if regression else [int(v) for v in fitted.classes_]
    if not regression and len(classes)==2:co=np.vstack((np.zeros(co.shape[1]),co[0]));inter=np.array([0.,inter[0]])
    artifact={'coefficients':co.tolist(),'intercepts':inter.tolist(),'classes':classes,'teams':teams,'participants':list(pi),'trainingRows':len(rows),'regularization':100. if regression else 1.,'fieldTransform':field_transform,'fitConverged':bool(regression or np.max(fitted.n_iter_)<400),'timeWeightHalfLifeDays':180,'timeWeightSource':'Predeclared six-month decay; not a validated coaching/injury causal coefficient.'}
    if regression:
        residual=np.asarray(labels)-fitted.predict(design);artifact.update(residuals={str(z):residual[np.array([min(2,r['field']//20) for r in rows])==z].tolist() for z in range(3)},allResiduals=residual.tolist())
    return artifact

def clock_key(r):
    half=r['clock']-1800 if r['clock']>1800 else r['clock']
    return CLOCK_KINDS.index(r['kind']),int(bool(r['complete'])),int(half<=120),0 if r['script']<-8 else 2 if r['script']>8 else 1

def clocks(rows,teams):
    # Dirichlet pooling strength is estimated by clock-mean variance components.
    # Every support value is an observed 0..90-second snap interval.
    grouped=defaultdict(lambda:defaultdict(list));fallback=defaultdict(list)
    for r in rows:
        if r['kind'] not in CLOCK_KINDS:continue
        if r['elapsed'] is None or not 0<=r['elapsed']<=90:continue
        grouped[clock_key(r)][r['o']].append(int(r['elapsed']));fallback[CLOCK_KINDS.index(r['kind'])].append(int(r['elapsed']))
    cdf=np.zeros((len(teams),len(CLOCK_KINDS),2,2,3,91));metadata=[]
    for kind in range(len(CLOCK_KINDS)):
      if not fallback[kind]:
          metadata.append({'kind':kind,'status':'unavailable_never_observed','observations':0});continue
      for complete in range(2):
       for hurry in range(2):
        for script in range(3):
         key=(kind,complete,hurry,script);by_team=grouped.get(key,{});vals=[v for vs in by_team.values() for v in vs] or fallback[kind];league=np.bincount(vals,minlength=91).astype(float);league/=league.sum();means=[np.mean(v) for v in by_team.values() if len(v)>=5];noise=[np.var(v)/len(v) for v in by_team.values() if len(v)>=5];between=max(0.,float(np.var(means)-np.mean(noise))) if len(means)>=3 else 0.;within=float(np.var(vals));kappa=float(np.clip(within/between-1,1,10000)) if between>0 else 10000.
         for i,t in enumerate(teams):
            counts=np.bincount(by_team.get(t,[]),minlength=91);p=(counts+kappa*league)/(counts.sum()+kappa);cdf[i,kind,complete,hurry,script]=np.cumsum(p)
         metadata.append({'key':list(key),'observations':len(vals),'empiricalPriorExposure':kappa,'fallbackToKind':not bool(by_team)})
    cdf[...,-1]=1.;return cdf.tolist(),metadata

def concentration(matrix):
    a=np.asarray(matrix,float);p=(a.sum(axis=0)+.5)/(a.sum()+.5*a.shape[1]);n=a.sum(axis=1)
    def nll(logk):
        alpha=p*np.exp(logk);return -float(np.sum(gammaln(alpha.sum())-gammaln(alpha.sum()+n)+np.sum(gammaln(a+alpha)-gammaln(alpha),axis=1)))
    fit=minimize_scalar(nll,bounds=(-3,12),method='bounded');return p.tolist(),float(np.exp(fit.x))

def enrich(model,rows,variant='team_eb'):
    if variant not in ('team_eb','team_eb_frailty'):raise ValueError('Unknown football variant')
    m=copy.deepcopy(model);sport=m['sport'];cutoff=m['fittingCutoff'];teams=m['teams'];plays=[r for r in rows if r['kind'] in CLOCK_KINDS];drops=[r for r in plays if r['kind'] in ('pass','sack')];passing=[r for r in drops if r['kind']=='pass' and r['complete']];rush=[r for r in plays if r['kind']=='rush'];pass_td=[int(r['yards']>=r['field'] and not r['fumble']) for r in passing];rush_td=[int(r['yards']>=r['field'] and not r['fumble']) for r in rush]
    m['play']=component(plays,[base.KINDS.index('pass' if r['kind']=='sack' else r['kind']) for r in plays],teams,cutoff)
    m['dropback']=component(drops,[0 if r['kind']=='sack' else 1 if r['int'] else 3 if r['complete'] else 2 for r in drops],teams,cutoff,[r['qb'] for r in drops])
    for key,rs,td,who in [('pass',passing,pass_td,'receiver'),('rush',rush,rush_td,'runner')]:
        non=[r for r,t in zip(rs,td) if not t];m[key+'Yards']=component(non,[r['yards'] for r in non],teams,cutoff,[r[who] for r in non],True);m[key+'Touchdown']=component(rs,td,teams,cutoff,[r[who] for r in rs],field_transform='log')
    m['clockCDF'],m['clockEvidence']=clocks(plays,teams);m['clockSupportedKinds']=[any(r['kind']==k for r in plays) for k in CLOCK_KINDS]
    # Method-of-moments excess game-level completion dispersion, removing
    # conditional Bernoulli sampling variance. No validation game enters.
    x=base.numeric(*[np.array([r[k] for r in drops]) for k in ('down','distance','field','clock','script','home')]);out=base.Predictor(m['dropback']);prob=out.probabilities(x,np.array([r['o'] for r in drops]),np.array([r['d'] for r in drops]),np.array([r['qb'] for r in drops]));ci=m['dropback']['classes'].index(3);pc=prob[:,ci];groups=defaultdict(lambda:np.zeros(3))
    for r,p in zip(drops,pc):groups[(r['game'],r['o'])]+=np.array([int(r['kind']=='pass' and r['complete'])-p,p*(1-p),1])
    eligible=[v for v in groups.values() if v[2]>=15 and v[1]>1];variance=max(0.,float(np.var([v[0]/v[1] for v in eligible])-np.mean([1/v[1] for v in eligible]))) if len(eligible)>=30 else 0.
    m.update(fitConverged=all(m[k].get('fitConverged',False) for k in ('play','dropback','passYards','rushYards','passTouchdown','rushTouchdown')),version=VERSION,variant=variant,completionFrailtySD=float(np.sqrt(min(variance,4.))),completionFrailtyEvidence={'teamGames':len(eligible),'excessLogitVariance':variance,'method':'Earlier-game residual variance minus Bernoulli measurement variance; 15-dropback minimum; numerical SD bound 2.'},productionEligible=False)
    m['sha256']=digest({k:v for k,v in m.items() if k!='sha256'});return m
