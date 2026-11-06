"""Opportunity/efficiency heads and distribution adapters, never game samples."""
from collections import defaultdict
import numpy as np
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import Ridge
from ..stat_models import StatModel,COUNTS
from ...opportunity_hurdle_v20 import HurdleProjection
from .data import LABELS

class BernoulliModel(StatModel):
    @property
    def estimand(self):return 'conditional_probability'

class CountModel(StatModel):
    def samples(self,rows,seed=240241,n=128):return np.rint(np.maximum(0,super().samples(rows,seed,n)))

class OpportunityPooling:
    """Shared team volume -> player share -> conditional efficiency.

    Unknown/new-player opportunity stays unassigned. Presence of a historical
    box row is not a verified availability assessment. Miss-based NBA exposure
    is explicitly a proxy, not observed on-court missed-shot opportunity.
    """
    family='opportunity_pooling';estimand='conditional_mean'
    def __init__(self,stat,rebound=False):self.stat=stat;self.rebound=rebound
    def fit(self,rows):
        if len(rows)<100:raise ValueError('One hundred earlier player observations required')
        valid=[r for r in rows if r.get('opportunity') is not None and r.get('actualTeamOpportunity',0)>0]
        if len(valid)<100:raise ValueError('Verified opportunity labels unavailable')
        self.scaler=StandardScaler().fit([r['x'] for r in valid]);z=np.clip(self.scaler.transform([r['x'] for r in valid]),-6,6)
        op=np.array([r['opportunity'] for r in valid],float);team=np.array([r['actualTeamOpportunity'] for r in valid],float);y=np.array([r['y'] for r in valid],float)
        if np.any(op<0) or np.any(op>team+1e-6):raise ValueError('Player opportunity exceeds official team total')
        unique={}
        for i,r in enumerate(valid):unique.setdefault((r['gameId'],r['team']),i)
        ix=list(unique.values());self.volume=Ridge(alpha=100).fit(z[ix,15:18],team[ix]);self.share=Ridge(alpha=100).fit(z,np.divide(op,team));self.kind=valid[0]['opportunityKind']
        exposure=op.copy();self.misses=None
        if self.rebound:
            if self.stat!='rebounds' or self.kind!='minutes':raise ValueError('Rebound exposure is NBA only')
            misses=np.array([r.get('actualGameMisses') or 0 for r in valid],float)
            if np.any(misses<=0):raise ValueError('Complete missed-shot box evidence required')
            self.misses=Ridge(alpha=100).fit(z[ix][:,[24,25,7,8]],misses[ix]);exposure=op/48*misses
        positive=exposure>0
        if positive.sum()<40:raise ValueError('Forty positive opportunity labels required')
        rates=np.divide(y[positive],exposure[positive]);self.player_rate={};self.population=float(np.average(rates,weights=np.sqrt(exposure[positive])))
        grouped=defaultdict(list)
        for i in np.flatnonzero(positive):grouped[valid[i]['player']].append(i)
        prior_strength=90 if self.kind=='minutes' else 30
        for p,indices in grouped.items():self.player_rate[p]=(y[indices].sum()+prior_strength*self.population)/(exposure[indices].sum()+prior_strength)
        base=np.array([self.player_rate.get(r['player'],self.population) for r in valid]);self.efficiency=Ridge(alpha=100).fit(z[positive],rates-base[positive],sample_weight=np.sqrt(exposure[positive]))
        self.training={'rows':len(valid),'teamCohorts':len(ix),'through':max(r['at'] for r in valid),'availabilityVerified':False,'reboundExposure':'minutes/48 times game misses; proxy' if self.rebound else None};return self
    def factors(self,rows):
        if any(k in r for r in rows for k in LABELS):raise ValueError('Outcome labels may not enter a forecast')
        z=np.clip(self.scaler.transform([r['x'] for r in rows]),-6,6);volume=np.maximum(0,self.volume.predict(z[:,15:18]));share=np.clip(self.share.predict(z),0,1)
        groups=defaultdict(list)
        for i,r in enumerate(rows):groups[(r['gameId'],r['team'])].append(i)
        for indices in groups.values():
            # Same team-volume features are shared across all players in a cohort.
            volume[indices]=float(np.mean(volume[indices]));den=share[indices].sum()
            if den>1:share[indices]/=den
        op=volume*share;exposure=op.copy()
        if self.misses is not None:exposure=op/48*np.maximum(0,self.misses.predict(z[:,[24,25,7,8]]))
        rate=np.maximum(0,np.array([self.player_rate.get(r['player'],self.population) for r in rows])+self.efficiency.predict(z))
        return {'teamVolume':volume,'share':share,'opportunity':op,'efficiency':rate,'estimate':exposure*rate,'exposure':exposure}
    def predict(self,rows):return self.factors(rows)['estimate']

class LegacyHurdle:
    """Refit V20 reference; explicitly not the production champion artifact."""
    family='v20_hurdle_refit';estimand='conditional_mean'
    def __init__(self,stat):self.stat=stat
    def fit(self,rows):self.model=HurdleProjection().fit(rows);return self
    def predict(self,rows):return self.model.predict(rows)

class ResidualDistribution:
    """Chronological residual law around a specialized expected-value head."""
    def __init__(self,point):self.point=point;self.stat=point.stat;self.estimand=point.estimand
    def calibrate_distribution(self,rows):
        from .data import features_only
        if len(rows)<30:raise ValueError('Independent residual-calibration sample required')
        p=self.point.predict(features_only(rows));self.residuals=np.array([r['y'] for r in rows])-p;self.calibrationGames=sorted({r['gameId'] for r in rows});return self
    def predict(self,rows):return self.point.predict(rows)
    def samples(self,rows,seed=240241,n=128):
        p=self.predict(rows);rng=np.random.default_rng(seed);draws=p[:,None]+rng.choice(self.residuals,size=(len(rows),n))
        if not self.stat.endswith('Yards'):draws=np.maximum(0,draws)
        if self.stat in COUNTS or self.stat.endswith('Attempts') or self.stat=='passingCompletions':draws=np.rint(draws)
        return draws

def candidate(family,stat,train,cal):
    if stat=='moneyline':
        if family not in ('rolling5','ewma','empirical_bayes','opponent_ridge','hierarchical','boosted'):raise ValueError('Bernoulli outcome needs a probability family')
        model=BernoulliModel(family,'doubleDouble').fit(train);model.stat='moneyline';return model.calibrate_distribution(cal)
    if family in ('opportunity_pooling','minutes_rebound_opportunity'):
        model=OpportunityPooling(stat,family=='minutes_rebound_opportunity').fit(train)
    elif family=='v20_hurdle_refit':model=LegacyHurdle(stat).fit(train)
    else:
        count=stat in ('passingCompletions','fieldGoalAttempts','threePointAttempts','freeThrowAttempts')
        model=(CountModel if count else StatModel)(family,'passingAttempts' if count else stat).fit(train)
        model.stat=stat
        if stat=='spread':model.nonnegative=False
        return model.calibrate_distribution(cal)
    return ResidualDistribution(model).calibrate_distribution(cal)

def mixture_samples(draws,weights,seed=240241):
    """Mixture distribution, not weighted averages that shrink predictive tails."""
    arrays=np.asarray(draws);weights=np.asarray(weights,float)
    if arrays.ndim!=3 or np.any(weights<0) or not np.isclose(weights.sum(),1) or len(weights)!=len(arrays):raise ValueError('Compatible normalized mixture required')
    rng=np.random.default_rng(seed);choice=rng.choice(len(arrays),size=arrays.shape[1:],p=weights)
    return np.take_along_axis(arrays,choice[None,:,:],axis=0)[0]

class MixtureModel:
    """Inner-selected marginal mixture; never a joint-game simulator."""
    def __init__(self,models,weights,stat):self.models=models;self.weights=np.asarray(weights);self.stat=stat;self.estimand='conditional_probability' if stat in ('moneyline','doubleDouble','tripleDouble') else 'conditional_mean'
    def predict(self,rows):return sum(w*m.predict(rows) for w,m in zip(self.weights,self.models))
    def samples(self,rows,seed=240241,n=128):return mixture_samples([m.samples(rows,seed+i+1,n) for i,m in enumerate(self.models)],self.weights,seed)
