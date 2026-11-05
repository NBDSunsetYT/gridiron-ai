"""Replay the active production historical-distribution source algorithm.

Not a substitute for unrecovered point-in-time roster/injury qualifications.
Current deployed learned artifacts must not leak into historical forecasts.
"""
from collections import defaultdict
import numpy as np
from ..prop_history import summarize
from ..hierarchical_props import attach_models
from .datasets import protected

def replay(raw,season,week,as_of):
    banned=protected()
    prior=[r for r in raw if r['game_id'] not in banned and r['position']=='QB' and r['season'] in (season-1,season) and (r['season']<season or r['week']<week) and sum(float(r.get(k) or 0) for k in ('attempts','carries','targets','receptions'))>0]
    logs=defaultdict(list);records=[];catalog={}
    for r in sorted(prior,key=lambda r:(r['season'],r['week'],r['game_id'])):
        pid=r['player_id'];v=float(r['passing_yards']);logs[pid].append({'id':r['game_id'],'season':r['season'],'week':r['week'],'values':{'passingYards':v}});catalog[pid]={'id':pid,'position':'QB'};records.append({'player':pid,'position':'QB','season':r['season'],'week':r['week'],'game':r['game_id'],'stat':'passingYards','value':v})
    players={pid:summarize(rs) for pid,rs in logs.items()};artifacts=attach_models(players,list(catalog.values()),records,season,as_of=as_of);out={}
    for pid,stats in players.items():
        d=stats['passingYards'];n=d['sampleSize'];emp=sum(b['value']*b['count'] for b in d['histogram'])/n;h=d.get('hierarchical');mean=emp
        if h:
            base=h['base']
            if base['family']=='student_t' and base['df']<=1:raise ValueError('Production distribution has no finite expectation')
            base_mean=base.get('location',base.get('mean'));mean=(n*emp+h['strength']*base_mean)/(n+h['strength'])
        out[pid]={'mean':float(mean),'method':'hierarchical' if h else 'empirical_history','historicalGameIds':d['historicalGameIds'],'sampleSize':n,'regularization':bool(d.get('regularization'))}
    return out,artifacts
