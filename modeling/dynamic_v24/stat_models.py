"""Fixed, appropriate per-stat model families with inner-only distributions."""
import numpy as np
from scipy.sparse import csr_matrix,hstack
from scipy.stats import poisson,nbinom
from sklearn.preprocessing import StandardScaler,OneHotEncoder
from sklearn.linear_model import Ridge,Lasso,ElasticNet,LogisticRegression,PoissonRegressor
from sklearn.ensemble import HistGradientBoostingRegressor,GradientBoostingRegressor
from sklearn.mixture import GaussianMixture

FAMILIES=('rolling5','ewma','opponent_ridge','lasso','elastic_net','hierarchical','boosted','quantile','negative_binomial','hurdle','mixture','empirical_bayes','hybrid')
COUNTS={'passingAttempts','passingTouchdowns','interceptions','carries','rushingTouchdowns','targets','receptions','receivingTouchdowns','points','rebounds','assists','threePointersMade','steals','blocks','turnovers','teamPoints','pointsReboundsAssists','pointsRebounds','pointsAssists','reboundsAssists'}

class StatModel:
    def __init__(self,family,stat):self.family=family;self.stat=stat
    @property
    def estimand(self):return 'conditional_median' if self.family=='quantile' else 'conditional_probability' if self.stat in ('doubleDouble','tripleDouble') else 'conditional_mean'
    def fit(self,rows):
        if len(rows)<60:raise ValueError('Sixty chronological fit observations required')
        self.scaler=StandardScaler().fit([r['x'] for r in rows]);z=np.clip(self.scaler.transform([r['x'] for r in rows]),-6,6);y=np.array([r['y'] for r in rows]);f=self.family;self.nonnegative=not self.stat.endswith('Yards');self.encoder=None;self.model=None
        self.binary=self.stat in ('doubleDouble','tripleDouble');self.population={role:float(np.mean([r['y'] for r in rows if r['role']==role])) for role in {r['role'] for r in rows}}
        if self.binary and f not in ('rolling5','ewma','empirical_bayes','opponent_ridge','hierarchical','boosted'):raise ValueError('Binary outcome requires a probability model')
        if f=='negative_binomial' and self.stat not in COUNTS:raise ValueError('Count family is inappropriate for this statistic')
        if f in ('rolling5','ewma','empirical_bayes'):return self
        if f=='hierarchical':
            self.encoder=OneHotEncoder(handle_unknown='ignore').fit([[r['player'],r['team']] for r in rows]);z=hstack([csr_matrix(z),self.encoder.transform([[r['player'],r['team']] for r in rows])],format='csr')
        if self.binary:
            if len(set(y))<2:raise ValueError('Binary event has no trainable class variation')
            if f=='boosted':
                from sklearn.ensemble import HistGradientBoostingClassifier
                self.model=HistGradientBoostingClassifier(max_iter=35,max_leaf_nodes=8,min_samples_leaf=30,l2_regularization=20,early_stopping=False,random_state=24024).fit(z,y)
            else:self.model=LogisticRegression(C=.1,max_iter=200).fit(z,y)
        elif f=='boosted':self.model=HistGradientBoostingRegressor(max_iter=35,max_leaf_nodes=8,min_samples_leaf=30,l2_regularization=20,early_stopping=False,random_state=24024).fit(z,y)
        elif f=='quantile':self.model=GradientBoostingRegressor(loss='quantile',alpha=.5,n_estimators=35,max_depth=2,min_samples_leaf=30,random_state=24024).fit(z,y)
        elif f=='lasso':self.model=Lasso(alpha=.05,max_iter=1000).fit(z,y)
        elif f=='elastic_net':self.model=ElasticNet(alpha=.1,l1_ratio=.5,max_iter=1000).fit(z,y)
        elif f=='negative_binomial':self.model=PoissonRegressor(alpha=1,max_iter=200).fit(z,np.maximum(0,y))
        elif f=='hurdle':
            positive=y>0;self.presence=LogisticRegression(C=.1,max_iter=200).fit(z,positive) if 0<positive.sum()<len(y) else None;self.positive_probability=float(positive.mean())
            if positive.sum()<30:raise ValueError('Thirty positive fit observations required for hurdle')
            self.model=Ridge(alpha=50).fit(z[positive],np.log1p(y[positive]));self.log_bias=float(np.mean(np.exp(np.log1p(y[positive])-self.model.predict(z[positive]))))
        elif f=='hybrid':
            op=np.array([r.get('opportunity') if r.get('opportunity') is not None else np.nan for r in rows]);valid=np.isfinite(op)&(op>0)
            if valid.sum()<60:raise ValueError('Verified training opportunity volume unavailable')
            self.model=Ridge(alpha=50).fit(z[valid],op[valid]);self.efficiency=Ridge(alpha=100).fit(z[valid],y[valid]/op[valid],sample_weight=np.sqrt(op[valid]))
        else:self.model=Ridge(alpha=50,solver='lsqr').fit(z,y)
        return self
    def design(self,rows):
        z=np.clip(self.scaler.transform([r['x'] for r in rows]),-6,6)
        return hstack([csr_matrix(z),self.encoder.transform([[r['player'],r['team']] for r in rows])],format='csr') if self.encoder else z
    def predict(self,rows):
        f=self.family
        if f=='rolling5':p=np.array([r['baseline'] for r in rows])
        elif f=='ewma':p=np.array([r['ewma'] for r in rows])
        elif f=='empirical_bayes':p=np.array([(r['priorCount']*r['baseline']+5*self.population.get(r['role'],r['baseline']))/(r['priorCount']+5) for r in rows])
        else:
            z=self.design(rows);p=self.model.predict_proba(z)[:,1] if self.binary else self.model.predict(z)
            if f=='hurdle':p=(self.presence.predict_proba(z)[:,1] if self.presence else self.positive_probability)*np.maximum(0,np.exp(np.minimum(12,p))*self.log_bias-1)
            if f=='hybrid':p=np.maximum(0,p)*np.maximum(0,self.efficiency.predict(z))
        return np.clip(p,0,1) if self.binary else np.maximum(0,p) if self.nonnegative else p
    def calibrate_distribution(self,rows):
        if len(rows)<30:raise ValueError('Thirty independent chronological inner-calibration observations required')
        p=self.predict(rows);y=np.array([r['y'] for r in rows]);self.residuals=y-p;self.dispersion=max(0,float(np.sum((y-p)**2-p)/max(1,np.sum(p*p))));self.mixture=None
        if self.family=='mixture' and len(rows)>=60:self.mixture=GaussianMixture(2,covariance_type='diag',reg_covar=.01,random_state=24024).fit(self.residuals[:,None])
        if self.family=='hurdle':
            pos=y>0
            if pos.sum()<10:raise ValueError('Ten positive inner-calibration outcomes required')
            self.positive_log_residuals=np.log1p(y[pos])-self.model.predict(self.design([r for r,ok in zip(rows,pos) if ok]))
        self.distribution_calibration_games=sorted({r['gameId'] for r in rows});return self
    def samples(self,rows,seed=24024,n=96):
        p=self.predict(rows);rng=np.random.default_rng(seed)
        if self.binary:draws=rng.binomial(1,p[:,None],size=(len(rows),n))
        elif self.family=='hurdle':
            z=self.design(rows);presence=self.presence.predict_proba(z)[:,1] if self.presence else np.full(len(rows),self.positive_probability);log=self.model.predict(z);positive=np.maximum(1 if self.stat in COUNTS else 1e-9,np.expm1(np.minimum(12,log[:,None]+rng.choice(self.positive_log_residuals,size=(len(rows),n)))));draws=positive*(rng.random((len(rows),n))<presence[:,None])
        elif self.family=='negative_binomial':
            a=self.dispersion;draws=nbinom.rvs(1/a,1/(1+a*np.maximum(p,1e-9)),size=(n,len(p)),random_state=rng).T if a>.001 else rng.poisson(np.maximum(p,0),size=(n,len(p))).T
        elif self.mixture is not None:
            labels=rng.choice(2,size=(len(rows),n),p=self.mixture.weights_);draws=p[:,None]+self.mixture.means_.ravel()[labels]+rng.normal(size=(len(rows),n))*np.sqrt(self.mixture.covariances_.ravel()[labels])
        else:draws=p[:,None]+rng.choice(self.residuals,size=(len(rows),n))
        if self.nonnegative:draws=np.maximum(0,draws)
        if self.stat in COUNTS:draws=np.rint(draws)
        return draws

def metrics(rows,pred,samples):
    y=np.array([r['y'] for r in rows]);error=np.asarray(pred)-y;lo,hi=np.quantile(samples,[.05,.95],axis=1);ordered=np.sort(samples,axis=1);n=ordered.shape[1];pair=np.sum((2*np.arange(1,n+1)-n-1)*ordered,axis=1)/(n*n);crps=np.mean(np.abs(samples-y[:,None]),axis=1)-pair
    zero=np.mean(samples==0,axis=1);truth=(y==0).astype(float);bins=np.digitize(zero,np.linspace(0,1,6)[1:-1]);ece=sum(np.mean(bins==b)*abs(float(np.mean(zero[bins==b])-np.mean(truth[bins==b]))) for b in range(5) if np.any(bins==b))
    return {'observations':len(rows),'games':len({r['gameId'] for r in rows}),'mae':float(np.mean(abs(error))),'rmse':float(np.sqrt(np.mean(error*error))),'bias':float(np.mean(error)),'medianAbsoluteError':float(np.median(abs(error))),'interval90Coverage':float(np.mean((y>=lo)&(y<=hi))),'crps':float(np.mean(crps)),'zeroEventBrier':float(np.mean((zero-truth)**2)),'zeroEventECE':float(ece),'verifiedLineCalibration':None,'properScoreScope':'Conditional marginal distribution only, not a coherent game or verified market threshold'}

def paired(rows,before,after,seed=24024,alpha=.05/48):
    ids=sorted({r['gameId'] for r in rows});y=np.array([r['y'] for r in rows]);d=[]
    for gid in ids:
        ix=[i for i,r in enumerate(rows) if r['gameId']==gid];d.append(float(np.mean(abs(np.asarray(after)[ix]-y[ix])-abs(np.asarray(before)[ix]-y[ix]))))
    rng=np.random.default_rng(seed);d=np.array(d);resampled=np.mean(d[rng.integers(0,len(d),size=(2000,len(d)))],axis=1)
    return {'games':len(ids),'meanGameMAEDelta':float(np.mean(d)),'CI95':np.quantile(resampled,[.025,.975]).tolist(),'deltaCIAdjusted':np.quantile(resampled,[alpha/2,1-alpha/2]).tolist(),'alphaAdjusted':alpha,'negativeFavorsCandidate':True,'cluster':'game'}
