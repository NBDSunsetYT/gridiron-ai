"""Separate league registries for explicit opportunity and efficiency heads."""
from collections import defaultdict
from .quality import aware
from ..opportunity_hurdle_v20 import HurdleProjection
class LeagueOpportunityModels:
    def __init__(self,sport):
        if sport not in ('NFL','CFB','NBA'):raise ValueError('Separate supported league required')
        self.sport=sport;self.models={};self.unsupported={}
    def fit(self,rows,cutoff):
        if any(aware(r['at'])>=aware(cutoff) for r in rows):raise ValueError('Future training outcome/event in pregame model fit')
        if any(r.get('sport',self.sport)!=self.sport for r in rows):raise ValueError('Cannot pool football and basketball or NFL and CFB labels')
        groups=defaultdict(list)
        for r in rows:
            if r['player']!='__team__':groups[r['stat']].append(r)
        for stat,items in groups.items():
            try:self.models[stat]=HurdleProjection().fit(items)
            except ValueError as e:self.unsupported[stat]=str(e)
        self.cutoff=cutoff;return self
    def predict(self,stat,rows):
        if stat not in self.models:raise ValueError(self.unsupported.get(stat,'Opportunity/efficiency evidence unavailable'))
        if any(aware(r['at'])<=aware(self.cutoff) for r in rows):raise ValueError('Evaluation must follow training cutoff')
        return self.models[stat].predict(rows)
