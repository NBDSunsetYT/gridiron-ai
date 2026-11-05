"""Estimate game-level residual heterogeneity on chronological TRAINING holdouts.
The initial in-sample variance estimator collapsed to zero in both leagues.
This estimator withholds the last 28 training days; it never sees the graded game.
Positive heterogeneity may include parameter/lineup drift, not a causal injury effect.
"""
from datetime import timedelta
from collections import defaultdict
import numpy as np
from ..football_v15 import Predictor,numeric
from .football_fit import component
from .evidence import aware

def estimate(rows,games,cutoff):
    middle=aware(cutoff)-timedelta(days=28);core_ids={gid for gid,g in games.items() if aware(g['lastObservedAt'])+timedelta(hours=6)<middle};test_ids={gid for gid,g in games.items() if aware(g['firstObservedAt'])>=middle and aware(g['lastObservedAt'])+timedelta(hours=6)<aware(cutoff)};core=[r for r in rows if r['game'] in core_ids and r['kind'] in ('pass','sack')];held=[r for r in rows if r['game'] in test_ids and r['kind'] in ('pass','sack')]
    if len(core)<1000 or len(held)<500:return {'sd':0.,'status':'insufficient_earlier_training_holdout','corePlays':len(core),'heldoutPlays':len(held)}
    teams=sorted({r[k] for r in core for k in ('o','d')});model=component(core,[0 if r['kind']=='sack' else 1 if r['int'] else 3 if r['complete'] else 2 for r in core],teams,middle.isoformat(),[r['qb'] for r in core]);x=numeric(*[np.array([r[k] for r in held]) for k in ('down','distance','field','clock','script','home')]);probs=Predictor(model).probabilities(x,np.array([r['o'] for r in held]),np.array([r['d'] for r in held]),np.array([r['qb'] for r in held]));ps=probs[:,model['classes'].index(3)];groups=defaultdict(lambda:np.zeros(3))
    for r,p in zip(held,ps):groups[(r['game'],r['o'])]+=np.array([int(r['kind']=='pass' and r['complete'])-p,p*(1-p),1])
    eligible=[v for v in groups.values() if v[2]>=15 and v[1]>1];eta=np.array([v[0]/v[1] for v in eligible]);sampling=np.array([1/v[1] for v in eligible]);variance=max(0.,float(np.var(eta)-sampling.mean())) if len(eta)>=30 else 0.
    return {'sd':float(np.sqrt(min(variance,4.))),'excessLogitVariance':variance,'status':'estimated_on_training_holdout' if len(eta)>=30 else 'insufficient_team_games','coreGames':len({r['game'] for r in core}),'heldoutGames':len({r['game'] for r in held}),'heldoutTeamGames':len(eligible),'coreEnd':max(r['at'] for r in core),'heldoutStart':min(r['at'] for r in held),'heldoutEnd':max(r['at'] for r in held),'holdoutBoundary':middle.isoformat(),'fitConverged':model['fitConverged'],'meanResidualLogitShift':float(eta.mean()) if len(eta) else None,'rawGameResidualVariance':float(np.var(eta)) if len(eta) else None,'bernoulliMeasurementVariance':float(sampling.mean()) if len(sampling) else None,'precision':'Approximate variance component from held-out standardized completion residuals. Hyperparameter and missing-availability uncertainty remain unquantified.'}
