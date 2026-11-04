"""Predeclared, separate opportunity/efficiency projection families.
These are statistical projections, not independent pretend Monte Carlo games.
"""
import numpy as np
from scipy.sparse import hstack,csr_matrix
from sklearn.preprocessing import StandardScaler,OneHotEncoder
from sklearn.linear_model import Ridge
from sklearn.ensemble import HistGradientBoostingRegressor

FAMILIES=('rolling5','ridge','hierarchical','boosted','hybrid')
OPPORTUNITY={'passingYards':'passingAttempts','receivingYards':'targets','receptions':'targets','rushingYards':'carries','points':'minutes','rebounds':'minutes','assists':'minutes','steals':'minutes','blocks':'minutes','turnovers':'minutes','fieldGoalAttempts':'minutes','threePointAttempts':'minutes','freeThrowAttempts':'minutes'}

class Projection:
    def __init__(self,family):
        if family not in FAMILIES:raise ValueError('Unknown projection family')
        self.family=family
    def fit(self,rows):
        self.names=rows[0]['featureNames'];self.stat=rows[0]['stat'];x=np.asarray([r['x'] for r in rows]);y=np.asarray([r['y'] for r in rows]);self.scaler=StandardScaler().fit(x);z=self.scaler.transform(x)
        if self.family=='rolling5':return self
        if self.family=='hierarchical':
            self.enc=OneHotEncoder(handle_unknown='ignore').fit([[r['player'],r['team']] for r in rows]);z=hstack([csr_matrix(z),self.enc.transform([[r['player'],r['team']] for r in rows])],format='csr')
        if self.family=='boosted':self.model=HistGradientBoostingRegressor(max_iter=70,max_leaf_nodes=12,min_samples_leaf=40,l2_regularization=10,learning_rate=.06,early_stopping=False,random_state=18001).fit(z,y)
        else:self.model=Ridge(alpha=20,solver='lsqr').fit(z,y)
        if self.family=='hybrid' and self.stat in OPPORTUNITY:
            op=OPPORTUNITY[self.stat];oi=self.names.index(op+'_mean5');past=x[:,oi];valid=past>0
            # Fit efficiency using OBSERVED training opportunities; the future
            # opportunities below are predictions, not observed final workloads.
            observed=np.asarray([r.get('opportunity',0.) for r in rows]);valid=observed>0
            self.rate=None
            if sum(valid)>=100:
                self.rate=Ridge(alpha=40,solver='lsqr').fit(z[valid],y[valid]/observed[valid],sample_weight=np.sqrt(observed[valid]))
        return self
    def predict(self,rows,opportunities=None):
        if self.family=='rolling5':return np.asarray([r['baseline'] for r in rows])
        x=self.scaler.transform(np.asarray([r['x'] for r in rows]))
        if self.family=='hierarchical':x=hstack([csr_matrix(x),self.enc.transform([[r['player'],r['team']] for r in rows])],format='csr')
        pred=np.maximum(0,self.model.predict(x))
        if self.family=='hybrid' and getattr(self,'rate',None) is not None:
            if opportunities is None:raise ValueError('Predicted opportunities are required for hybrid efficiency')
            pred=np.maximum(0,self.rate.predict(x))*np.maximum(0,opportunities)
        return pred

def error_metrics(y,p):
    e=np.asarray(p)-np.asarray(y)
    return {'observations':len(e),'mae':float(np.mean(abs(e))),'rmse':float(np.sqrt(np.mean(e*e))),'bias':float(np.mean(e)),'medianAbsoluteError':float(np.median(abs(e)))}

def cluster_delta(rows,before,after,seed=18018):
    game_ids=sorted({r['gameId'] for r in rows});d=[];before=np.asarray(before);after=np.asarray(after);ys=np.asarray([r['y'] for r in rows]);ix={g:[] for g in game_ids}
    for i,r in enumerate(rows):ix[r['gameId']].append(i)
    for g,indices in ix.items():d.append(float(np.mean(abs(after[indices]-ys[indices]))-np.mean(abs(before[indices]-ys[indices]))))
    if not d:return None
    rng=np.random.default_rng(seed);d=np.asarray(d);sample=np.mean(d[rng.integers(0,len(d),size=(1000,len(d)))],axis=1)
    return {'gameCount':len(d),'meanGameMAEDelta':float(np.mean(d)),'bootstrap95':np.quantile(sample,[.025,.975]).tolist(),'negativeFavorsCandidate':True,'resamplingUnit':'game'}
