"""Recency-weighted opportunity rates with player-specific Gamma-Poisson pooling.
Prior exposure is fitted on earlier player holdouts, never the graded games.
"""
from collections import defaultdict,Counter
import copy
import numpy as np
from scipy.special import gammaln
from scipy.optimize import minimize_scalar
from ..iterative_learning import digest
from .evidence import aware
VERSION='nba-recency-usage-eb-19.0.0'
RATE_KEYS=('field_goals_attempted','three_point_field_goals_attempted','free_throws_attempted','offensive_rebounds','defensive_rebounds','assists','steals','blocks','turnovers','fouls')

def enrich(base,games,cutoff):
    m=copy.deepcopy(base);history=defaultdict(list);valid=[]
    keys=('field_goals_made','three_point_field_goals_made','free_throws_made','points',*RATE_KEYS)
    for g in sorted(games.values(),key=lambda g:(g['at'],g['id'])):
        if (aware(cutoff)-aware(g['at'])).total_seconds()<=6*3600:continue
        for tid,t in g['teams'].items():
            ps=[p for p in g['players'] if str(p['team_id'])==str(tid) and float(p.get('minutes') or 0)>0];mins=sum(float(p['minutes']) for p in ps)
            if len(ps)<5 or not 235<=mins<=400 or sum(p['points'] for p in ps)!=t['team_score']:continue
            valid.append((g,tid,t,mins))
            for p in ps:history[str(p['athlete_id'])].append((g['at'],p))
    tau={};fit_counts={}
    for key in RATE_KEYS:
        rates=[];counts=[];exposures=[]
        for h in history.values():
            if len(h)<8:continue
            older=h[:-3];recent=h[-3:];r=(sum(float(p.get(key) or 0) for d,p in older)+.5)/(sum(float(p['minutes']) for d,p in older)+1)
            rates.append(r);counts.append(sum(float(p.get(key) or 0) for d,p in recent));exposures.append(sum(float(p['minutes']) for d,p in recent))
        rates,counts,exposures=map(np.asarray,(rates,counts,exposures))
        if len(counts)<30:raise ValueError('Insufficient earlier NBA opportunity holdouts')
        def loss(log_tau):
            t=np.exp(log_tau);alpha=rates*t;return -float(np.sum(gammaln(alpha+counts)-gammaln(alpha)+alpha*(np.log(t)-np.log(t+exposures))+counts*(np.log(exposures)-np.log(t+exposures))))
        fit=minimize_scalar(loss,bounds=(0,np.log(2000)),method='bounded');tau[key]=float(np.exp(fit.x));fit_counts[key]=len(counts)
    league=Counter()
    for h in history.values():
        for date,p in h:
            for key in (*keys,'minutes'):league[key]+=float(p.get(key) or 0)
    players={};overrides={}
    for pid,h in history.items():
        weighted=Counter();career=Counter()
        older=Counter()
        for date,p in h[:-5]:
            for key in (*keys,'minutes'):older[key]+=float(p.get(key) or 0)
        for date,p in h[-5:]:
            w=np.exp2(-(aware(cutoff)-aware(date)).total_seconds()/86400/60.)
            for key in (*keys,'minutes'):weighted[key]+=float(p.get(key) or 0)*w;career[key]+=float(p.get(key) or 0)
        prior=lambda key:(older[key]+.5)/(older['minutes']+1) if older['minutes'] else (league[key]-career[key]+.5)/(league['minutes']-career['minutes']+1)
        players[pid]=dict(weighted);overrides[pid]={key:(weighted[key]+tau[key]*prior(key))/(weighted['minutes']+tau[key]) for key in RATE_KEYS}
        two=(weighted['field_goals_attempted']-weighted['three_point_field_goals_attempted']);prior_two=max(0.,prior('field_goals_attempted')-prior('three_point_field_goals_attempted'));t=tau['field_goals_attempted'];overrides[pid]['two_point_field_goals_attempted']=(two+t*prior_two)/(weighted['minutes']+t)
    m.update(version=VERSION,candidate='recency_usage_eb',variant='rotation_bootstrap',players=players,rateOverrides=overrides,recencyHalfLifeDays=60,usageEvidence={'gammaPoissonPriorMinutes':tau,'priorFitPlayerCohorts':fit_counts,'validTeamBoxes':len(valid),'historicalLineupPublicationVerified':False,'recentGameWindow':5,'priorAndRecentGamesDisjoint':True})
    m['sha256']=digest({k:v for k,v in m.items() if k!='sha256'});return m
