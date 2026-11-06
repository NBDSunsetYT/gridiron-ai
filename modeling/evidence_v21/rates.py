"""Research opportunity/efficiency heads, with no invented availability weights.

Rates shrink historical exposure-weighted player observations toward a learned
league/role prior. The shrinkage exposure and opponent residual coefficient
are fitted on earlier training games only, separately for each league.
"""
from collections import defaultdict
import numpy as np
from sklearn.linear_model import Ridge
from ..structural_v18.models import OPPORTUNITY
from ..accuracy_v20.quality import aware

def proportional_budget(values,total,cap):
    """KL projection onto a capped simplex; zeros retain zero mass."""
    v=np.maximum(0,np.asarray(values,float))
    if not np.all(np.isfinite(v)) or cap<=0 or total<0 or (v>0).sum()*cap<total:
        raise ValueError('Positive supported workloads cannot satisfy the budget')
    if total==0:return np.zeros(len(v))
    lo,hi=0.,max(1.,total/np.min(v[v>0]))
    for _ in range(80):
        m=(lo+hi)/2
        if np.minimum(cap,v*m).sum()<total:lo=m
        else:hi=m
    out=np.minimum(cap,v*(lo+hi)/2)
    if abs(out.sum()-total)>1e-7:raise AssertionError('Minutes budget failed')
    return out

class HierarchicalRates:
    def __init__(self,sport):
        if sport not in ('NFL','CFB','NBA'):raise ValueError('Separate supported league required')
        self.sport=sport
    def fit(self,rows,cutoff):
        if any(aware(r['at'])>=aware(cutoff) for r in rows):raise ValueError('Future rate training observation')
        self.cutoff=cutoff;self.parameters={};groups=defaultdict(list)
        for r in rows:
            if r['player']!='__team__' and r['stat'] in OPPORTUNITY and r.get('opportunity',0)>0:groups[(r['stat'],r['role'])].append(r)
        for (stat,role),rs in groups.items():
            if len(rs)<50:continue
            y=np.asarray([r['y'] for r in rs],float);n=np.asarray([r['opportunity'] for r in rs],float);mu=float(y.sum()/n.sum());rates=y/n
            # Empirical-Bayes pseudo-exposure: variance decomposition of the
            # observed rate into sampling noise and persistent player spread.
            by=defaultdict(list)
            for r in rs:by[r['player']].append(r)
            player_rates=np.asarray([sum(r['y'] for r in rr)/sum(r['opportunity'] for r in rr) for rr in by.values()]);within=float(np.average((rates-mu)**2,weights=n));between=float(np.var(player_rates))
            tau=float(np.clip(within/max(between,1e-9),1,100))
            op=OPPORTUNITY[stat];x=[];res=[];weights=[]
            for r in rs:
                f=dict(zip(r['featureNames'],r['x']));prior=(5*max(0,f[stat+'_mean5'])+tau*mu)/(5*max(0,f[op+'_mean5'])+tau);opp_y=f['opponent_allowed_'+stat];opp_o=f['opponent_allowed_'+op];x.append([opp_y/max(opp_o,1)-mu]);res.append(r['y']/r['opportunity']-prior);weights.append(r['opportunity'])
            adjustment=Ridge(alpha=100).fit(x,res,sample_weight=np.sqrt(weights))
            self.parameters[(stat,role)]={'mean':mu,'priorExposure':tau,'opponentAdjustment':adjustment,'trainingObservations':len(rs),'players':len(by)}
        return self
    def predict(self,rows,opportunities):
        if len(rows)!=len(opportunities) or any(aware(r['at'])<=aware(self.cutoff) for r in rows):raise ValueError('Prediction must follow training')
        result=[]
        for r,o in zip(rows,opportunities):
            p=self.parameters.get((r['stat'],r['role']))
            if p is None:raise ValueError('No independently trained role efficiency prior')
            f=dict(zip(r['featureNames'],r['x']));op=OPPORTUNITY[r['stat']];n=min(5,f['team_games']);rate=(n*max(0,f[r['stat']+'_mean5'])+p['priorExposure']*p['mean'])/(n*max(0,f[op+'_mean5'])+p['priorExposure']);rate+=float(p['opponentAdjustment'].predict([[f['opponent_allowed_'+r['stat']]/max(1,f['opponent_allowed_'+op])-p['mean']]])[0]);rate=max(0,rate)
            if r['stat']=='receptions':rate=min(1,rate)
            result.append(max(0,float(o))*rate)
        return np.asarray(result)

def factor_attribution(predicted,actual):
    """Exact symmetric product decomposition; descriptive, never causal."""
    import itertools,math
    a=np.asarray(predicted,float);b=np.asarray(actual,float)
    if len(a)!=len(b) or not np.all(np.isfinite(a)) or not np.all(np.isfinite(b)):raise ValueError('Finite matched factors required')
    out=np.zeros(len(a));perms=list(itertools.permutations(range(len(a))))
    for order in perms:
        state=b.copy()
        for j in order:
            old=float(np.prod(state));state[j]=a[j];out[j]+=float(np.prod(state))-old
    out/=len(perms)
    if not math.isclose(out.sum(),float(np.prod(a)-np.prod(b)),abs_tol=1e-7):raise AssertionError('Attribution failed to reconcile')
    return out.tolist()
