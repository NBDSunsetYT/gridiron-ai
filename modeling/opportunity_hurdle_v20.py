"""Experimental two-part opportunity/efficiency projections, research only.

Dense regressions give a positive workload to low-participation players. This
candidate first estimates a nonzero-opportunity event, then its conditional
volume, then efficiency. It does not create pretend simulated game samples.
Hyperparameters are fixed before new validation windows, not tuned on them.
"""
import numpy as np
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import Ridge,LogisticRegression
from .structural_v18.models import OPPORTUNITY

VERSION='opportunity-hurdle-candidate-20.0.0'
class HurdleProjection:
    def fit(self,rows):
        if len(rows)<100:raise ValueError('One hundred chronological training rows required')
        self.names=rows[0]['featureNames'];self.stat=rows[0]['stat'];x=np.asarray([r['x'] for r in rows],float);self.scaler=StandardScaler().fit(x);z=self.scaler.transform(x);y=np.asarray([r['y'] for r in rows],float)
        self.opportunity=OPPORTUNITY.get(self.stat,self.stat);op=np.asarray([r['opportunity'] if self.stat in OPPORTUNITY else r['y'] for r in rows],float);positive=op>0
        if positive.sum()<40:raise ValueError('Forty observed nonzero opportunity rows required')
        self.always=float(positive.mean());self.presence=None
        if positive.sum()<len(rows):self.presence=LogisticRegression(C=.05,max_iter=300,solver='lbfgs',random_state=20020).fit(z,positive)
        self.volume=Ridge(alpha=100,solver='lsqr').fit(z[positive],op[positive]);self.rate=None
        if self.stat in OPPORTUNITY:self.rate=Ridge(alpha=100,solver='lsqr').fit(z[positive],y[positive]/op[positive],sample_weight=np.sqrt(op[positive]))
        self.training={'rows':len(rows),'nonzeroRows':int(positive.sum()),'lastTrainingGame':max(r['at'] for r in rows),'volumeRidgeAlpha':100,'efficiencyRidgeAlpha':100,'presenceC':.05,'opportunity':self.opportunity,'version':VERSION};return self
    def predict(self,rows):
        z=self.scaler.transform(np.asarray([r['x'] for r in rows],float));p=self.presence.predict_proba(z)[:,1] if self.presence is not None else np.full(len(rows),self.always);volume=np.maximum(0,self.volume.predict(z));estimate=p*volume
        if self.rate is not None:estimate*=np.maximum(0,self.rate.predict(z))
        return estimate
