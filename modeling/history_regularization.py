"""Predeclared Jeffreys beta-binomial estimate, gated by chronological evidence.

This is conditional on a recorded participation game. It neither creates game
simulations nor fits injury, roster, opponent or weather adjustments. Raw K/N
remains available. No learned parameter or threshold uses the test outcomes.
"""
from collections import defaultdict
import hashlib
import json
from functools import lru_cache
from pathlib import Path
import numpy as np

VERSION='jeffreys-player-history-12.3.0'
WINDOW=24
_cache={}


@lru_cache(maxsize=4)
def frozen_validation(test_season):
    try:
        value=json.loads((Path(__file__).parent/'validated'/f'history-validation-nfl-{test_season}.json').read_text())
        return value if value.get('sport')=='NFL' and value.get('testSeason')==test_season and value.get('protocol')=='predeclared-jeffreys24-v1' else None
    except (OSError,ValueError):return None


def publication_regularization(records,stat,position,season,sport,as_of=None):
    # A prior-season replication is frozen independently of the current holdout.
    # No NFL artifact is transferred into an unsupported college cohort.
    frozen=frozen_validation(season-1) if sport=='NFL' else None
    previous=(frozen or {}).get('cohorts',{}).get(stat+':'+position)
    if not previous or not previous.get('approved'):return {'approved':False,'reason':'Independent prior-season replication did not pass, or is unavailable for this sport/cohort.'}
    # Validation is an offline release artifact, never an expensive per-visitor
    # re-training job or a moving test-set selection. Each promotion is versioned.
    current_artifact=frozen_validation(season) or {}
    from .fit import utc
    try:
        if not as_of or utc(current_artifact['createdAt'])>utc(as_of):return {'approved':False,'reason':'The validation artifact was not available at the prediction timestamp.'}
    except (ValueError,KeyError):return {'approved':False,'reason':'A verified artifact availability timestamp is required.'}
    candidate=current_artifact.get('cohorts',{}).get(stat+':'+position)
    if not candidate:return {'approved':False,'reason':'A frozen current-season monitoring artifact is unavailable.'}
    current=dict(candidate)
    if current.get('approved'):
        current['priorValidation']=previous['validation']
        current['availableAt']=current_artifact['createdAt']
        current['artifactId']=hashlib.sha256(json.dumps([current['artifactId'],previous['artifactId']],sort_keys=True).encode()).hexdigest()
        current['reason']='Predeclared smoothing passed independent prior-season replication and current chronological monitoring.'
    return current


def audit_regularization(records,stat,position,season,sport='NFL'):
    rows=sorted([r for r in records if r['stat']==stat and r['position']==position],key=lambda r:(r['season'],r['week'],r['game'],r['player']))
    key=hashlib.sha256(json.dumps([VERSION,sport,stat,position,season,[(r['player'],r['game'],r['season'],r['week'],r['value']) for r in rows]],sort_keys=True).encode()).hexdigest()
    if key in _cache:return _cache[key]
    result=_audit(rows,stat,position,season,sport)
    if len(_cache)>=64:_cache.pop(next(iter(_cache)))
    _cache[key]=result
    return result


def _audit(rows,stat,position,season,sport):
    identities=[(r['player'],r['season'],r['week']) for r in rows]
    if len(set(identities))!=len(identities):return {'approved':False,'reason':'Ambiguous or duplicated player-week chronology; no within-week order was inferred.'}
    prior=[r for r in rows if r['season']<season]
    current=[r for r in rows if r['season']==season]
    if len(prior)<30:return {'approved':False,'reason':'Prior-season threshold coverage is insufficient.'}
    thresholds=sorted({float(np.floor(v)+.5) for v in np.quantile([r['value'] for r in prior],[.2,.4,.6,.8])})
    histories=defaultdict(list)
    for r in prior:histories[r['player']].append(r['value'])
    raw=[];predicted=[];outcomes=[];games=[];weeks=[];limited=0
    for r in current:
        past=histories[r['player']][-WINDOW:]
        if past:
            hits=np.count_nonzero(np.asarray(past)[:,None]>np.asarray(thresholds)[None,:],axis=0)
            raw.extend(hits/len(past));predicted.extend((hits+.5)/(len(past)+1));outcomes.extend(int(r['value']>k) for k in thresholds);games.extend([r['game']]*len(thresholds));weeks.extend([r['week']]*len(thresholds));limited+=int(len(past)<5)*len(thresholds)
        histories[r['player']].append(r['value'])
    if len(outcomes)<100 or len(set(games))<8:return {'approved':False,'reason':'Chronological holdout coverage is insufficient.'}
    p,b,y=map(np.asarray,(predicted,raw,outcomes));delta=(p-y)**2-(b-y)**2
    grouped=defaultdict(list)
    for game,value in zip(games,delta):grouped[game].append(float(value))
    sums=np.array([sum(v) for v in grouped.values()]);sizes=np.array([len(v) for v in grouped.values()]);rng=np.random.default_rng(12300)
    # Resample games, never correlated player-threshold rows as if independent.
    indices=rng.integers(0,len(sums),size=(5000,len(sums)));means=sums[indices].sum(axis=1)/sizes[indices].sum(axis=1)
    ci=np.quantile(means,[.025,.975]).tolist();family=52 if sport=='NFL' else 13
    adjusted=min(1.,family*(1+int(np.sum(means>=0)))/(len(means)+1))
    # Adjacent weeks also share players and teams. Require a second, more
    # conservative circular two-week block sensitivity check before promotion.
    weekly=defaultdict(list)
    for week,value in zip(weeks,delta):weekly[week].append(float(value))
    ws=np.array([sum(v) for _,v in sorted(weekly.items())]);wn=np.array([len(v) for _,v in sorted(weekly.items())])
    starts=rng.integers(0,len(ws),size=(5000,(len(ws)+1)//2));blocks=np.stack([starts,(starts+1)%len(ws)],axis=2).reshape(5000,-1)[:,:len(ws)]
    week_means=ws[blocks].sum(axis=1)/wn[blocks].sum(axis=1);week_ci=np.quantile(week_means,[.025,.975]).tolist()
    week_p=min(1.,family*(1+int(np.sum(week_means>=0)))/(len(week_means)+1))
    def log_loss(q):
        q=np.clip(q,1e-9,1-1e-9);return float(-np.mean(y*np.log(q)+(1-y)*np.log1p(-q)))
    validation={'chronological':True,'testSeason':season,'thresholdsFromSeasons':sorted({r['season'] for r in prior}),'thresholds':thresholds,'testPredictions':len(y),'testGames':len(sums),'brierScore':float(np.mean((p-y)**2)),'benchmarkBrier':float(np.mean((b-y)**2)),'logLoss':log_loss(p),'benchmarkLogLoss':log_loss(b),'pairedGameBootstrapBrierDifference95':ci,'familywiseAdjustedPValue':adjusted,'familySize':family,'familywiseAlpha':.025,'limitedSampleTestPredictions':limited,'calibrated':False,'scope':'Retrospective player-stat thresholds against unsmoothed historical K/N; not historical market prices, source-first-publication evidence, prospective contract accuracy or a matchup model.'}
    validation.update(testWeeks=len(ws),weekBlockSize=2,pairedWeekBlockBootstrapBrierDifference95=week_ci,weekBlockAdjustedPValue=week_p)
    approved=ci[1]<0 and adjusted<=.025 and week_ci[1]<0 and week_p<=.025 and len(ws)>=8 and validation['logLoss']<=validation['benchmarkLogLoss']
    result={'version':VERSION,'sport':sport,'statistic':stat,'position':position,'priorAlpha':.5,'priorBeta':.5,'window':WINDOW,'validation':validation,'approved':bool(approved),'reason':'Predeclared smoothing improved chronological Brier and log loss.' if approved else 'Smoothing did not pass the conservative publication gate.'}
    result['artifactId']=hashlib.sha256(json.dumps(result,sort_keys=True).encode()).hexdigest()
    return result
