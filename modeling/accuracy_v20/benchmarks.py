"""A learned opponent adjustment to rolling averages, trained on earlier games.
No market probability enters this independent projection benchmark.
"""
import numpy as np
from sklearn.linear_model import Ridge
class OpponentAdjustedRolling:
    def fit(self,rows):
        if len(rows)<30:raise ValueError('Thirty earlier observations required')
        self.index=rows[0]['featureNames'].index('opponent_allowed_'+rows[0]['stat']);allowed=np.asarray([r['x'][self.index] for r in rows]);self.league=float(allowed.mean())
        if self.league<=0:raise ValueError('Opponent exposure denominator unavailable')
        x=np.asarray([r['baseline']*(r['x'][self.index]/self.league-1) for r in rows]);y=np.asarray([r['y']-r['baseline'] for r in rows]);self.model=Ridge(alpha=100,fit_intercept=False).fit(x[:,None],y);self.lastTrainingAt=max(r['at'] for r in rows);return self
    def predict(self,rows):
        x=np.asarray([r['baseline']*(r['x'][self.index]/self.league-1) for r in rows]);return np.maximum(0,np.asarray([r['baseline'] for r in rows])+self.model.predict(x[:,None]))
