"""Research QB opportunity -> completion -> yards/completion factorization.

The multinomial denominator includes unassigned/new-player team opportunities.
It never transfers those attempts to an arbitrary identified quarterback.
"""
from collections import defaultdict
import numpy as np
from scipy.optimize import minimize
from scipy.special import logsumexp,softmax
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression,Ridge
from ..opportunity_hurdle_v20 import HurdleProjection
from ..accuracy_v20.quality import aware

def share_features(row):
    if row is None:return np.array([0.,0.,0.,0.,0.,0.,1.])
    f=dict(zip(row['featureNames'],row['x']));return np.array([1.,np.log1p(max(0,row['baseline'])),max(0,row['baseline'])/max(1,f['team_passingAttempts']),f['participation3'],f['participation5'],np.log1p(max(0,f['passingAttempts_last'])),0.])

class PassingChain:
    def fit(self,rows,cutoff):
        if any(aware(r['at'])>=aware(cutoff) for r in rows):raise ValueError('Future training observation')
        self.cutoff=cutoff;teams=[r for r in rows if r['player']=='__team__' and r['stat']=='passingAttempts'];self.volume=HurdleProjection().fit(teams);totals={(r['gameId'],r['team']):r['y'] for r in teams};groups=defaultdict(list)
        for r in rows:
            if r['player']!='__team__' and r['stat']=='passingAttempts':groups[(r['gameId'],r['team'])].append(r)
        cohorts=[]
        for key,rs in groups.items():
            total=totals.get(key);known=sum(r['y'] for r in rs)
            if total is None or total<known-1e-6:raise ValueError('Identified attempts exceed team opportunities')
            if total>0:cohorts.append((np.stack([*[share_features(r) for r in rs],share_features(None)]),np.array([*[r['y'] for r in rs],total-known],float)))
        if len(cohorts)<30:raise ValueError('Thirty earlier team opportunity cohorts required')
        def objective(beta):
            loss=50*float(beta@beta);grad=100*beta.copy()
            for x,y in cohorts:
                z=x@beta;p=softmax(z);loss+=y.sum()*logsumexp(z)-y@z;grad+=x.T@(y.sum()*p-y)
            return loss,grad
        result=minimize(objective,np.zeros(7),jac=True,method='L-BFGS-B',options={'maxiter':200,'ftol':1e-10})
        if not result.success:raise ValueError('Opportunity allocation fit did not converge')
        self.beta=result.x;positive=[r for r in rows if r['player']!='__team__' and r['stat']=='passingYards' and r.get('actualAttempts',0)>0];self.scaler=StandardScaler().fit([r['x'] for r in positive]);x=self.scaler.transform([r['x'] for r in positive]);c=np.array([r['actualCompletions'] for r in positive]);n=np.array([r['actualAttempts'] for r in positive]);y=np.array([r['y'] for r in positive])
        if np.any(c<0) or np.any(c>n):raise ValueError('Official completion/attempt counts conflict')
        xx=np.repeat(x,2,axis=0);labels=np.tile([1,0],len(x));weights=np.column_stack([c,n-c]).ravel();use=weights>0;self.completion=LogisticRegression(C=.05,max_iter=300,random_state=22022).fit(xx[use],labels[use],sample_weight=weights[use]);use=c>0;self.yards=Ridge(alpha=100,solver='lsqr').fit(x[use],y[use]/c[use],sample_weight=np.sqrt(c[use]));self.training={'teamCohorts':len(cohorts),'completionPlayerGames':len(positive),'interceptAndSlopeRegularization':'Multinomial L2 100, binomial C .05, yards Ridge100; fixed before grading'};return self
    def predict_team(self,rows):
        if any(aware(r['at'])<=aware(self.cutoff) for r in rows):raise ValueError('Prediction must follow model fit')
        team=[r for r in rows if r['player']=='__team__' and r['stat']=='passingAttempts'];rs=[r for r in rows if r['player']!='__team__' and r['stat']=='passingAttempts'];yard={r['player']:r for r in rows if r['stat']=='passingYards' and r['player']!='__team__'}
        if len(team)!=1 or not rs:raise ValueError('Identified earlier QBs and a unique team budget required')
        total=float(self.volume.predict(team)[0]);p=softmax(np.stack([*[share_features(r) for r in rs],share_features(None)])@self.beta);out={};factors={}
        for r,w in zip(rs,p):
            pid=r['player'];attempts=total*float(w);out[(pid,'passingAttempts')]=attempts
            if pid in yard:
                x=self.scaler.transform([yard[pid]['x']]);rate=float(self.completion.predict_proba(x)[0,1]);ypc=float(self.yards.predict(x)[0]);out[(pid,'passingYards')]=attempts*rate*ypc;factors[pid]={'teamAttempts':total,'opportunityShare':float(w),'completionRate':rate,'yardsPerCompletion':ypc,'availability':'unknown unless separately verified; share is not an availability probability'}
        unassigned=total*float(p[-1])
        if abs(sum(v for (pid,s),v in out.items() if s=='passingAttempts')+unassigned-total)>1e-6:raise AssertionError('Team opportunities failed reconciliation')
        return out,{'teamAttempts':total,'unassignedAttempts':unassigned,'factors':factors,'unassignedIsNotAFictionalQB':True}
