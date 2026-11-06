"""Opponent-adjusted EPA and fitted conditional event offsets, research only.

All fits require observations strictly before the target cutoff. Ridge tuning
uses blocked earlier/later dates. Weekly Gaussian filtering is conditional on
the fitted opponent effects, not a complete posterior over football outcomes.
No market prices or final scores enter these fits.
"""
from collections import defaultdict,Counter
from copy import deepcopy
import hashlib,json,math
import numpy as np
from scipy.optimize import minimize
from scipy.special import expit,logsumexp
from sklearn.linear_model import Ridge
from .fit import utc

VERSION='opponent-epa-ratings-18.0.0'
RATED_VERSION='football-market-ratings-18.1.0'

def filter_source_table(table,mask):
    """An empty eligibility mask is still Boolean, never an Arrow null mask."""
    import pyarrow as pa
    if len(mask)!=table.num_rows:raise ValueError('Source eligibility mask length differs')
    return table.filter(pa.array(mask,type=pa.bool_()))

def sha(value):
    return hashlib.sha256(json.dumps({k:v for k,v in value.items() if k!='sha256'},sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()

def _groups(rows,sport,season,cutoff):
    cut=utc(cutoff);groups=defaultdict(list)
    if not rows or sport not in ('NFL','CFB'):raise ValueError('Separate real league evidence required')
    for r in rows:
        if r['sport']!=sport or int(r['season'])!=season or utc(r['at'])>=cut or utc(r['eventAt'])>utc(r['at']):raise ValueError('EPA rows must strictly precede the event fitting cutoff in the exact league/season')
        if r.get('availableAt') and utc(r['availableAt'])>=cut:raise ValueError('EPA edition was unavailable before cutoff')
        if not r.get('sourceVersion') or not r['o'] or not r['d'] or r['o']==r['d'] or not math.isfinite(float(r['epa'])):raise ValueError('Finite, identified and versioned EPA observations required')
        groups[(r['game'],r['o'],r['d'])].append(r)
    out=[]
    for (game,o,d),rs in groups.items():
        if len({(r['eventAt'],r['home']) for r in rs})!=1:raise ValueError('Conflicting game identity/home evidence')
        values=np.array([r['epa'] for r in rs],float)
        out.append({'game':game,'o':o,'d':d,'eventAt':rs[0]['eventAt'],'lastAt':max(r['at'] for r in rs),'home':float(rs[0]['home']),
                    'rest':rs[0].get('restDifference'),'epa':float(values.mean()),'plays':len(rs),
                    'varianceOfMean':float(values.var(ddof=1)/len(values)) if len(values)>1 else None})
    return sorted(out,key=lambda r:(r['eventAt'],r['game'],r['o']))

def _design(groups,teams):
    ti={t:i for i,t in enumerate(teams)};x=np.zeros((len(groups),2*len(teams)+2))
    for i,g in enumerate(groups):
        x[i,ti[g['o']]]=1;x[i,len(teams)+ti[g['d']]]=-1;x[i,-2]=2*g['home']-1
        x[i,-1]=float(g['rest']) if g['rest'] is not None else 0
    return x

def _filter(observations,phi,q,prior,keep=False):
    states={};nll=0.
    for o in observations:
        mean,var,last=states.get(o['key'],(0.,prior,o['time']));dt=max(0.,(o['time']-last)/604800)
        decay=phi**dt if dt else 1.;process=q*dt if abs(phi-1)<1e-8 else q*(1-decay**2)/max(1e-12,1-phi**2)
        mean*=decay;var=var*decay**2+process;innovation=max(1e-12,var+o['variance']);error=o['value']-mean
        nll+=.5*(math.log(2*math.pi*innovation)+error*error/innovation);gain=var/innovation
        states[o['key']]=(mean+gain*error,max(0.,(1-gain)*var),o['time'])
    return states if keep else nll

def fit_ratings(rows,sport,season,cutoff,alphas=(1.,10.,100.)):
    if any(not math.isfinite(a) or a<=0 for a in alphas):raise ValueError('Positive preregistered ridge grid required')
    gs=_groups(rows,sport,season,cutoff);teams=sorted({g[k] for g in gs for k in ('o','d')});x=_design(gs,teams);y=np.array([g['epa'] for g in gs]);days=sorted({g['eventAt'][:10] for g in gs})
    if len(days)<8 or len({g['game'] for g in gs})<12:raise ValueError('At least twelve games and eight chronological dates required')
    blocks=np.array_split(days,4);folds=[];losses={str(a):[] for a in alphas}
    for b in range(1,4):
        valid=np.array([g['eventAt'][:10] in blocks[b] for g in gs]);first=min(utc(g['eventAt']) for g,m in zip(gs,valid) if m);train=np.array([utc(g['lastAt'])<first for g in gs])
        if train.sum()<4:continue
        assert max(utc(g['lastAt']) for g,m in zip(gs,train) if m)<first
        folds.append({'trainLastAt':max(g['lastAt'] for g,m in zip(gs,train) if m),'validationFirstEventAt':first.isoformat(),'trainingRows':int(train.sum()),'validationRows':int(valid.sum())})
        for alpha in alphas:
            m=Ridge(alpha=alpha,solver='lsqr').fit(x[train],y[train]);losses[str(alpha)].append(float(np.mean((m.predict(x[valid])-y[valid])**2)))
    if len(folds)<2:raise ValueError('Two valid blocked chronological ridge folds required')
    alpha=min(alphas,key=lambda a:(np.mean(losses[str(a)]),a));m=Ridge(alpha=alpha,solver='lsqr').fit(x,y);residual=y-m.predict(x)
    noise=max(1e-12,float(np.mean(residual**2)));cov=np.linalg.inv(x.T@x+alpha*np.eye(x.shape[1]))*noise;count=Counter(g[k] for g in gs for k in ('o','d'))
    ridge={t:{'offense':float(m.coef_[i]),'defense':float(m.coef_[len(teams)+i]),'offenseSD':float(np.sqrt(cov[i,i])),
              'defenseSD':float(np.sqrt(cov[len(teams)+i,len(teams)+i])),'gamesPlayed':count[t]/2} for i,t in enumerate(teams)}
    observations=[]
    for g in gs:
        home=float(m.coef_[-2])*(2*g['home']-1);rest=float(m.coef_[-1])*(g['rest'] or 0);center=g['epa']-float(m.intercept_)-home-rest
        variance=max(1e-12,g['varianceOfMean'] if g['varianceOfMean'] is not None else noise)
        observations.extend([{'key':g['o']+':offense','value':center+ridge[g['d']]['defense'],'variance':variance+ridge[g['d']]['defenseSD']**2,'time':utc(g['eventAt']).timestamp()},
                             {'key':g['d']+':defense','value':ridge[g['o']]['offense']-center,'variance':variance+ridge[g['o']]['offenseSD']**2,'time':utc(g['eventAt']).timestamp()}])
    prior=max(noise,float(np.var(m.coef_[:2*len(teams)])),1e-12)
    fitted=minimize(lambda p:_filter(observations,p[0],math.exp(p[1]),prior),[.9,math.log(max(prior*.1,1e-10))],bounds=[(0.,1.),(math.log(1e-10),math.log(max(10.,prior*10)))],method='L-BFGS-B',options={'maxiter':100})
    if not fitted.success:raise ValueError('Weekly process fit did not converge; no candidate artifact')
    phi=float(fitted.x[0]);q=float(math.exp(fitted.x[1]));states=_filter(observations,phi,q,prior,True)
    artifact={'version':VERSION,'sport':sport,'season':season,'fittingCutoff':utc(cutoff).isoformat(),'trainingLastAt':max(r['at'] for r in rows),
              'sourceVersions':sorted({r['sourceVersion'] for r in rows}),'publicationAvailabilityVerified':all(bool(r.get('availableAt')) for r in rows),
              'teams':teams,'ridge':ridge,'leagueMeanEPA':float(m.intercept_),'homeFieldCoefficient':float(m.coef_[-2]),
              'restCoefficient':float(m.coef_[-1]) if any(g['rest'] is not None for g in gs) else None,
              'ridgeAlpha':alpha,'blockedCV':{'folds':folds,'losses':losses},'trainingGames':len({g['game'] for g in gs}),'trainingPlays':len(rows),
              'weekly':{'regressionToMean':phi,'processVariance':q,'priorVariance':prior,'posterior':{k:{'mean':v[0],'variance':v[1],'lastTimestamp':v[2]} for k,v in states.items()}},
              'lastGame':{t:max(g['eventAt'] for g in gs if t in (g['o'],g['d'])) for t in teams},
              'uncertainty':'Conditional on ridge opponent estimates and observation variances; not full model/availability uncertainty',
              'shrinkage':'Gaussian ridge partial pooling; precision grows with prior team games, with zero-centered league priors',
              'productionEligible':False}
    artifact['sha256']=sha(artifact);return artifact

def validate(artifact):
    if artifact.get('version')!=VERSION or artifact.get('sha256')!=sha(artifact):raise ValueError('Rating artifact version/checksum mismatch')

def matchup(artifact,home,away,event_start,variant='bayesian'):
    validate(artifact);event=utc(event_start)
    if event<=utc(artifact['fittingCutoff']) or home==away or any(t not in artifact['teams'] for t in (home,away)):raise ValueError('Supported distinct teams and strictly later event required')
    if event.year!=artifact['season'] and not(event.year==artifact['season']+1 and event.month<=2):raise ValueError('Separate league/season rating artifact required')
    values={}
    for t in (home,away):
        values[t]={}
        for role in ('offense','defense'):
            if variant=='ridge':mean=artifact['ridge'][t][role];sd=artifact['ridge'][t][role+'SD']
            elif variant=='bayesian':
                p=artifact['weekly']['posterior'][t+':'+role];dt=max(0,(event.timestamp()-p['lastTimestamp'])/604800);phi=artifact['weekly']['regressionToMean'];decay=phi**dt;q=artifact['weekly']['processVariance'];extra=q*dt if abs(phi-1)<1e-8 else q*(1-decay**2)/max(1e-12,1-phi**2);mean=p['mean']*decay;sd=math.sqrt(max(0,p['variance']*decay**2+extra))
            else:raise ValueError('Explicit ridge or Bayesian rating variant required')
            values[t][role]=mean;values[t][role+'SD']=sd
    rest=[(event-utc(artifact['lastGame'][t])).total_seconds()/86400 for t in (home,away)]
    return values,rest[0]-rest[1]

def _mle(z,base,y,family,ridge=1.,variance=1.):
    width=z.shape[1];classes=base.shape[1] if family=='multinomial' else 1
    def objective(flat):
        b=flat.reshape(classes,width);eta=base+z@b.T
        if family=='multinomial':
            ll=logsumexp(eta,axis=1)-eta[np.arange(len(y)),y];p=np.exp(eta-logsumexp(eta,axis=1)[:,None]);p[np.arange(len(y)),y]-=1;grad=p.T@z
        elif family=='yard_mean_log_link':
            mean=np.exp(np.clip(eta[:,0],-30,30));ll=.5*(mean-y)**2/variance;grad=(((mean-y)*mean/variance)[:,None]*z).sum(axis=0)[None,:]
        else:
            hazard=np.exp(np.clip(eta[:,0],-30,20));prob=-np.expm1(-hazard);prob=np.clip(prob,1e-12,1-1e-12);ll=-y*np.log(prob)-(1-y)*np.log1p(-prob);grad=(((prob-y)*hazard/prob)[:,None]*z).sum(axis=0)[None,:]
        return float(ll.sum()+ridge/2*np.sum(b*b)),(grad+ridge*b).ravel()
    result=minimize(objective,np.zeros(classes*width),jac=True,method='L-BFGS-B',options={'maxiter':400})
    if not result.success:raise ValueError('Conditional rating offset failed MLE convergence')
    return {'family':family,'coefficients':result.x.reshape(classes,width).tolist(),'ridge':ridge,'observations':len(y)}

def fit_offsets(rows,base_model,artifact):
    from .football_v15 import Predictor,numeric,_MARKET_KINDS
    validate(artifact)
    if base_model['sport']!=artifact['sport'] or base_model['version']!='football-market-candidate-18.0.0':raise ValueError('First migrate the exact league base artifact to Stage 1')
    if any(utc(r['at'])>=utc(artifact['fittingCutoff']) or r['sport']!=artifact['sport'] for r in rows):raise ValueError('Offset fits must strictly precede the target cutoff')
    out=deepcopy(artifact);heads={};index={t:i for i,t in enumerate(artifact['teams'])}
    usable=[r for r in rows if r['o'] in index and r['d'] in index and r.get('down') and r['kind'] in (*_MARKET_KINDS,'sack')]
    at=utc(artifact['fittingCutoff']).timestamp();phi=artifact['weekly']['regressionToMean'];means={}
    for team in artifact['teams']:
        means[team]={}
        for role in ('offense','defense'):
            state=artifact['weekly']['posterior'][team+':'+role];means[team][role]=state['mean']*phi**max(0,(at-state['lastTimestamp'])/604800)
    def design(rs):
        return np.array([[means[r['o']]['offense'],means[r['d']]['defense'],2*r['home']-1,float(r.get('restDifference') or 0)] for r in rs])
    for name in ('play','dropback','passYards','rushYards','passTouchdown','rushTouchdown'):
        if name not in base_model:continue
        classes=base_model[name]['classes'];rs=[];labels=[]
        for r in usable:
            if name=='play':label=_MARKET_KINDS.index('pass' if r['kind']=='sack' else r['kind']);ok=label in classes
            elif name=='dropback':label=0 if r['kind']=='sack' else 1 if r.get('int') else 3 if r.get('complete') else 2;ok=r['kind'] in ('pass','sack')
            else:
                passing=name.startswith('pass');ok=r['kind']==('pass' if passing else 'rush') and (not passing or r.get('complete'));td=int(r['yards']>=r['field'] and not r.get('fumble'));label=td if name.endswith('Touchdown') else r['yards']
                if name.endswith('Yards') and ('passTouchdown' if passing else 'rushTouchdown') in base_model:ok=ok and not td
            if ok:rs.append(r);labels.append(label)
        if len(rs)<30:raise ValueError('Insufficient supported offset observations: '+name)
        x=numeric(*[np.array([r[k] for r in rs]) for k in ('down','distance','field','clock','script','home')]);participant=None if name=='play' else np.array([r['qb'] if name=='dropback' else r.get('receiver') if name.startswith('pass') else r.get('runner') for r in rs]);p=Predictor(base_model[name]);base=p.predict(x,np.array([r['o'] for r in rs]),np.array([r['d'] for r in rs]),participant);z=design(rs)
        if name in ('play','dropback'):
            y=np.array([classes.index(v) for v in labels]);head=_mle(z,base,y,'multinomial');head['classes']=classes
        elif name.endswith('Yards'):
            supported=base[:,0]>0
            if supported.sum()<30:raise ValueError('Positive baseline conditional yard mean unavailable')
            variance=max(1e-12,float(np.var(base_model[name]['allResiduals'])));head=_mle(z[supported],np.log(base[supported]),np.array(labels)[supported],'yard_mean_log_link',variance=variance);head['unmodifiedNonPositiveBaseMeans']=int((~supported).sum());head['variance']=variance;head['scope']='Working Gaussian mean likelihood, signed outcomes and existing empirical residual law; separate TD hurdle excluded'
        else:
            probabilities=np.exp(base-logsumexp(base,axis=1)[:,None])[:,classes.index(1)];hazard=-np.log1p(-np.clip(probabilities,1e-12,1-1e-12));head=_mle(z,np.log(hazard)[:,None],np.array(labels),'touchdown_hazard');head['classes']=classes
        heads[name]=head
    out['offsets']=heads;out['baseModelSHA256']=base_model['sha256'];out['offsetFeatureOrder']=['offensiveEPA','defensiveEPA','homeSign','restDaysDifference'];out['offsetFitCutoff']=artifact['fittingCutoff'];out['offsetRatingVariant']='bayesian';out['sha256']=sha(out);return out

def attach(base_model,artifact):
    validate(artifact)
    if base_model['version']!='football-market-candidate-18.0.0' or artifact.get('baseModelSHA256')!=base_model['sha256'] or not artifact.get('offsets'):raise ValueError('Bound fitted offsets required; no untrained multipliers')
    out=deepcopy(base_model);out['version']=RATED_VERSION;out['ratings']=deepcopy(artifact);out['ratingsMigration']={'fromVersion':base_model['version'],'fromSHA256':base_model['sha256']};out['asOf']=max(utc(out['asOf']),utc(artifact['fittingCutoff'])).isoformat();out['sha256']=sha(out);return out

class Context:
    def __init__(self,artifact,teams,event_start):
        self.artifact=artifact;self.teams=teams;self.values,self.rest=matchup(artifact,*teams,event_start)
    def draw(self,rng,n):
        offense=np.stack([rng.normal(self.values[t]['offense'],self.values[t]['offenseSD'],n) for t in self.teams],axis=1);defense=np.stack([rng.normal(self.values[t]['defense'],self.values[t]['defenseSD'],n) for t in self.teams],axis=1)
        return np.stack([np.stack([offense[:,s],defense[:,1-s],np.full(n,1 if s==0 else -1),np.full(n,self.rest if s==0 else -self.rest)],axis=1) for s in (0,1)],axis=1)

class AdjustedPredictor:
    def __init__(self,name,base,artifact):self.name=name;self.base=base;self.head=artifact['offsets'].get(name);self.a=base.a
    def _adjust(self,value,x):
        if self.head is None:return value
        if x.shape[1]!=17:raise ValueError('Shared rating state missing from simulated play')
        offset=x[:,13:]@np.array(self.head['coefficients']).T;family=self.head['family']
        if family=='multinomial':return value+offset
        if family=='yard_mean_log_link':return np.where(value>0,value*np.exp(np.clip(offset,-30,30)),value)
        classes=self.head['classes'];p=np.exp(value-logsumexp(value,axis=1)[:,None])[:,classes.index(1)];hazard=-np.log1p(-np.clip(p,1e-12,1-1e-12))*np.exp(np.clip(offset[:,0],-30,20));prob=np.clip(-np.expm1(-hazard),1e-12,1-1e-12);result=np.empty_like(value);result[:,classes.index(1)]=np.log(prob);result[:,classes.index(0)]=np.log1p(-prob);return result
    def fast(self,x,side,participant=None,probabilities=False):
        value=self._adjust(self.base.fast(x[:,:13],side,participant,False),x)
        return np.exp(value-logsumexp(value,axis=1)[:,None]) if probabilities else value
    def predict(self,x,offense,defense,participant=None):return self._adjust(self.base.predict(x[:,:13],offense,defense,participant),x)
    def probabilities(self,x,offense,defense,participant=None):
        value=self.predict(x,offense,defense,participant);return np.exp(value-logsumexp(value,axis=1)[:,None])
