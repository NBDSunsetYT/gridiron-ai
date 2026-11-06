"""Learned event laws conditioned on generated history, preserving ledgers.

No dynamic multiplier exists. Invalid/unvalidated policies are rejected; sampled
event categories use fitted probabilities restricted to mechanically legal rows.
"""
from collections import Counter
import numpy as np
from .state import DynamicState
from .football import PlayKernel

class FootballPolicyKernel(PlayKernel):
    def __init__(self,*args,event_model=None,validation=None,**kwargs):
        super().__init__(*args,**kwargs);self.event_model=event_model;self.validation=validation or {}
        if event_model is not None:
            import hashlib,pickle
            self.input_hash=hashlib.sha256((self.input_hash+hashlib.sha256(pickle.dumps(event_model,protocol=5)).hexdigest()).encode()).hexdigest()
        if event_model is not None and not self.validation.get('conditionalEventLawAccepted'):raise ValueError('Unvalidated dynamic effect cannot change game draws')
        self.reset_policy()
    def reset_policy(self,initial=None):
        self.dynamic=DynamicState(self.sport,self.teams);self.action_row=None;self.previous_points=Counter()
        if initial and initial.get('dynamicState') is not None:
            from copy import deepcopy
            self.dynamic=deepcopy(initial['dynamicState'])
    def before_action(self,ledger,clock,team,down,distance,field):
        if clock is None:return
        self.dynamic.tick(clock.period,clock.remaining);self.dynamic.score.update({t:ledger.team[t]['points']-self.dynamic.score[t] for t in self.teams});self.previous_points=Counter({t:ledger.team[t]['points'] for t in self.teams});base,dyn=self.dynamic.features(team,down=down,distance=distance,field=field);base.update(team=team,opponent=next(t for t in self.teams if t!=team));self.action_row={'base':base,'dynamic':dyn}
    def select(self,rng,offense,down,field,clock,diff,overtime=False,period=4,distance=10):
        chosen=super().select(rng,offense,down,field,clock,diff,overtime,period,distance)
        if self.event_model is None or overtime:return chosen
        key=(offense,down,float(field),float(distance),period in (2,4) and clock<=120,int(np.sign(diff)),overtime,period in (2,4),tuple(sorted(self.unavailable)));pool=self.cache[key];p=self.event_model.predict([self.action_row])[0];classes=self.event_model.classes;by_kind={c:[r for r in pool if ('pass' if r['kind']=='sack' else 'rush' if r['kind']=='kneel' else r['kind'])==c] for c in classes};weights=np.array([p[i] if by_kind[c] else 0 for i,c in enumerate(classes)])
        if weights.sum()<=0:raise ValueError('Fitted law has no legal supported action')
        kind=classes[int(rng.choice(len(classes),p=weights/weights.sum()))];rows=by_kind[kind];return rows[int(rng.integers(len(rows)))].copy()
    def after_action(self,ledger,clock,team,kind,gain,complete,ended,actor):
        points=ledger.team[team]['points']-self.previous_points[team];self.dynamic.observe({'id':'sim:'+str(self.dynamic.version),'team':team,'kind':kind,'gain':gain,'success':gain>=self.action_row['base']['distance'],'actor':actor,'points':points,'possessionEnd':ended,'driveScored':points>0})

class BasketballPolicy:
    def __init__(self,teams,event_model,validation):
        if not validation.get('conditionalEventLawAccepted'):raise ValueError('Unvalidated dynamic event law')
        self.teams=tuple(teams);self.model=event_model;self.reset()
    def reset(self,initial=None):
        self.state=DynamicState('NBA',self.teams);self.version=0;self.last_score=Counter()
        if initial and initial.get('dynamicState') is not None:
            from copy import deepcopy
            self.state=deepcopy(initial['dynamicState'])
    def probabilities(self,ledger,period,remaining,team,baseline):
        for t,court in ledger.lineups.items():
            if self.state.lineups.get(t)!=court:self.state.set_lineup(t,court)
        self.state.tick(period,remaining);self.state.score.update({t:ledger.team[t]['points']-self.state.score[t] for t in self.teams});self.last_score=Counter({t:ledger.team[t]['points'] for t in self.teams});b,d=self.state.features(team);b.update(team=team,opponent=next(t for t in self.teams if t!=team),workload_minutes_missing=0.)
        # Current actor and shot quality are unknown before selecting a play.
        b={k:v for k,v in b.items() if not k.startswith('workload_actor') and k not in ('workload_consecutive_minutes','workload_fouls','workload_rest_since_exit')};d={k:v for k,v in d.items() if not k.startswith('recent_actor') and k not in ('fatigue_stint_square','fatigue_volume_interaction')};p=self.model.predict([{'base':b,'dynamic':d}])[0];order=['turnover','two','three','free_throws'];out=np.array([p[self.model.classes.index(k)] if k in self.model.classes else 0 for k in order]);return out/out.sum()
    def observe(self,ledger,period,remaining,team,kind,actor,ended):
        self.state.observe({'id':'sim:'+str(self.version),'team':team,'kind':kind,'actor':actor,'points':ledger.team[team]['points']-self.last_score[team],'gain':ledger.team[team]['points']-self.last_score[team],'success':ledger.team[team]['points']>self.last_score[team],'turnover':kind=='turnover','possessionEnd':ended});self.version+=1
