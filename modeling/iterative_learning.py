"""Offline champion/challenger evaluation primitives. Never writes user data.

Research selection is separate from production promotion. A replay with unknown
historical publication/injury availability cannot become a production champion.
All thresholds below are predeclared statistical diagnostics, NOT betting lines.
"""
from collections import defaultdict
from datetime import datetime, timezone
import gzip
import hashlib
import json
import math
from pathlib import Path
import numpy as np
from .audit_storage import write_snapshot_once

VERSION = 'iterative-research-protocol-16.0.0'
THRESHOLDS = {
    'passingYards': [149.5, 199.5, 249.5], 'rushingYards': [24.5, 49.5, 74.5],
    'receivingYards': [24.5, 49.5, 74.5], 'receptions': [2.5, 4.5, 6.5],
    'passingAttempts': [24.5, 34.5], 'completions': [14.5, 24.5],
    'passingTouchdowns': [.5, 1.5], 'rushingTouchdowns': [.5],
    'receivingTouchdowns': [.5], 'touchdowns': [.5], 'interceptions': [.5],
    'carries': [9.5, 19.5], 'points': [9.5, 19.5, 29.5],
    'rebounds': [3.5, 7.5, 11.5], 'assists': [2.5, 5.5, 8.5],
    'threePointersMade': [.5, 2.5], 'steals': [.5], 'blocks': [.5],
    'turnovers': [1.5, 3.5], 'pointsReboundsAssists': [24.5, 34.5, 44.5],
    'pointsRebounds': [24.5, 34.5], 'pointsAssists': [24.5, 34.5],
    'reboundsAssists': [9.5, 14.5], 'doubleDouble': [.5], 'tripleDouble': [.5],
}
CANDIDATES = [
    {'id': 'reference-v15', 'football': {}, 'nba': {}, 'description': 'Frozen previous research candidate; NOT a validated production champion.'},
    {'id': 'repair-conversions', 'football': {}, 'nba': {'recentGames': 10}, 'description': 'Preserve combined CFB TD/PAT observations; NBA ten-game team window.'},
    {'id': 'conditional-clock', 'football': {'conditionalClock': True}, 'nba': {'recentGames': 20, 'defenseShrinkage': True}, 'description': 'Observed situational clock cohorts; empirical-Bayes NBA opponent shrinkage.'},
    {'id': 'stronger-shrinkage', 'football': {'conditionalClock': True, 'regularization': 4}, 'nba': {'recentGames': 10, 'defenseShrinkage': True}, 'description': 'Stronger regularization of football identity/state effects; NBA short-window shrinkage.'},
]


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def freeze_json(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
    if path.suffix == '.gz': raw = gzip.compress(raw, mtime=0)
    if not write_snapshot_once(path, raw):
        if path.read_bytes() != raw: raise ValueError('Immutable artifact already exists with different contents: '+str(path))
    return hashlib.sha256(raw).hexdigest()


def probability(dist, threshold):
    bins = dist['histogram']; n = sum(b['count'] for b in bins)
    if n <= 0: raise ValueError('Empty simulation distribution')
    k = sum(b['count'] for b in bins if b['value'] > threshold)
    p = k/n
    from .simulator import wilson
    return {'successes': k, 'trials': n, 'rawProbability': p,
            'monteCarloSE': math.sqrt(p*(1-p)/n), 'interval95': wilson(k,n),
            'calibratedProbability': None}


def distribution_errors(dist, actual):
    bins = dist['histogram']; n = sum(b['count'] for b in bins)
    if not n or not math.isfinite(actual): raise ValueError('Finite outcome and nonempty distribution required')
    values = np.asarray([b['value'] for b in bins],float); weights = np.asarray([b['count'] for b in bins],float)/n
    cumulative = np.cumsum(weights)
    # Exact discrete CRPS: E|X-y| - .5 E|X-X'|, O(number of bins).
    pair_half = float(np.sum(weights*(values*(cumulative-weights)-np.cumsum(values*weights)+values*weights)))
    result = {'mean': float(np.sum(values*weights)), 'actual': float(actual),
              'crps': float(np.sum(weights*np.abs(values-actual))-pair_half), 'coverage': {}}
    result['error'] = result['mean']-actual
    for level in (.5,.8,.9,.95):
        low,high = [float(values[min(len(values)-1,int(np.searchsorted(cumulative,q)))]) for q in ((1-level)/2,1-(1-level)/2)]
        result['coverage'][str(level)] = {'lower': low, 'upper': high, 'covered': low <= actual <= high}
    return result


def unrealism_flags(forecast):
    """Internal accounting + deliberately broad safety rails, never score repair."""
    flags=[];n=forecast['simulations']
    for name,d in [('score:'+k,v) for k,v in forecast['scoreDistributions'].items()]+[(p+':'+s,d) for p,ss in forecast['players'].items() for s,d in ss.items()]:
        bins=d['histogram']
        if sum(b['count'] for b in bins)!=n:flags.append('distribution_mass:'+name)
        if any(b['count']<0 or not math.isfinite(b['value']) for b in bins):flags.append('invalid_distribution:'+name)
        if not math.isfinite(d['mean']):flags.append('nonfinite_mean:'+name)
    q=forecast['quality']
    if forecast['sport']=='NBA':
        if not all(q.get(k) for k in ('playerTeamPointsReconciled','minutesReconciled','combinedStatsShareOutcomes')):flags.append('basketball_accounting')
        for p,ss in forecast['players'].items():
            if ss.get('minutes',{}).get('mean',0)>55:flags.append('extreme_expected_minutes:'+p)
    elif not q.get('allGamesAccountingReconciled'):flags.append('football_accounting')
    # A broad diagnostic, not a tuned cap or adjustment to a forecast.
    if any(d['mean']<0 or d['mean']>(180 if forecast['sport']=='NBA' else 90) for d in forecast['scoreDistributions'].values()):flags.append('extreme_expected_team_score')
    return flags


def loss(p,y):
    p=min(1-1e-12,max(1e-12,p));return -y*math.log(p)-(1-y)*math.log1p(-p)


def evaluate_forecast(forecast, actual_scores, actual_players, game, baseline):
    home,away=forecast['home'],forecast['away']
    if set(actual_scores)!={home,away}:raise ValueError('Final team identity mismatch')
    score=[distribution_errors(forecast['scoreDistributions'][t],actual_scores[t]) for t in (home,away)]
    player=[];events=[];forecast_ids=set(forecast['players']);missing=[]
    for pid,ss in forecast['players'].items():
        observed=actual_players.get(pid)
        if observed is None:missing.append(pid);continue # Never turn unverified DNP into a zero.
        for stat,dist in ss.items():
            if stat not in observed['stats']:continue
            actual=observed['stats'][stat]
            if actual==0 and dist['mean']==0:continue
            row=distribution_errors(dist,actual)|{'id':pid,'stat':stat,'position':observed.get('position','unknown')}
            row['baseline']=baseline.get('players',{}).get(pid,{}).get(stat)
            player.append(row)
            for threshold in THRESHOLDS.get(stat,[]):
                p=probability(dist,threshold);y=int(actual>threshold)
                events.append({'id':pid,'stat':stat,'threshold':threshold,'outcome':y,**p,'brier':(p['rawProbability']-y)**2,'logLoss':loss(p['rawProbability'],y)})
    p=forecast['homeWinProbability'];winner=int(actual_scores[home]>actual_scores[away]);tie=actual_scores[home]==actual_scores[away]
    total=distribution_errors(forecast['totalDistribution'],sum(actual_scores.values()))
    margin=distribution_errors(forecast['marginDistribution'],actual_scores[home]-actual_scores[away])
    team_events=[]
    for name,dist,value,thresholds in [('total',forecast['totalDistribution'],sum(actual_scores.values()),[34.5,44.5,54.5] if forecast['sport']!='NBA' else [199.5,219.5,239.5]),('margin',forecast['marginDistribution'],actual_scores[home]-actual_scores[away],[-7.5,-.5,7.5])]:
        for threshold in thresholds:
            pr=probability(dist,threshold);y=int(value>threshold);team_events.append({'stat':name,'threshold':threshold,'outcome':y,**pr,'brier':(pr['rawProbability']-y)**2,'logLoss':loss(pr['rawProbability'],y)})
    joint=[]
    for q in forecast.get('jointResearchOutcomes',[]):
        a,b=q['left'],q['right'];pa,pb=actual_players.get(a['id']),actual_players.get(b['id'])
        if not pa or not pb or a['stat'] not in pa['stats'] or b['stat'] not in pb['stats']:continue
        y=int(pa['stats'][a['stat']]>a['threshold'] and pb['stats'][b['stat']]>b['threshold']);pr=q['successful']/q['trials']
        joint.append({**q,'outcome':y,'rawProbability':pr,'brier':(pr-y)**2,'logLoss':loss(pr,y)})
    teams=[]
    for tid,ss in forecast.get('teamDistributions',{}).items():
        for stat,dist in ss.items():
            values=[v['stats'][stat] for v in actual_players.values() if v['team']==tid and stat in v['stats']]
            if values:teams.append(distribution_errors(dist,sum(values))|{'team':tid,'stat':stat})
    return {'gameId':game['id'],'sport':game['sport'],'cohort':game['cohort'],'eventStart':game['at'],'phase':game['phase'],
            'score':score,'total':total,'margin':margin,'homeProbability':p,'actualHomeWin':winner,'tie':tie,
            'brier':None if tie else (p-winner)**2,'logLoss':None if tie else loss(p,winner),
            'player':player,'team':teams,'events':events,'teamEvents':team_events,'jointEvents':joint,
            'baselineScoreErrors':[baseline['scores'][t]-actual_scores[t] for t in (home,away)],
            'qualityFlags':unrealism_flags(forecast),'publicationVerified':False,'calibratedProbability':None,
            'coverage':{'forecastPlayers':len(forecast_ids),'matchedPlayers':len(forecast_ids&set(actual_players)),'unmatchedForecastIds':missing,
                        'unmodeledActualIds':sorted(set(actual_players)-forecast_ids)},
            'gameType':'blowout' if abs(actual_scores[home]-actual_scores[away])>=20 else 'close' if abs(actual_scores[home]-actual_scores[away])<=7 else 'other',
            'thresholdMeaning':'Fixed research CDF thresholds, NOT verified historical market quotes; no betting win-rate or edge claim.'}


def summary(rows):
    if not rows:return {'games':0}
    def means(values):
        a=np.asarray(values,float);return {'mae':float(np.abs(a).mean()),'rmse':float(np.sqrt(np.mean(a*a))),'bias':float(a.mean()),'medianAbsoluteError':float(np.median(np.abs(a)))} if len(a) else None
    def reliability(events):
        if not events:return None
        bins=[]
        for i in range(10):
            part=[r for r in events if min(9,int(r['p']*10))==i]
            if part:bins.append({'n':len(part),'meanPredicted':float(np.mean([r['p'] for r in part])),'observed':float(np.mean([r['y'] for r in part]))})
        return {'n':len(events),'brier':float(np.mean([(r['p']-r['y'])**2 for r in events])),
                'logLoss':float(np.mean([loss(r['p'],r['y']) for r in events])),
                'ece':sum(b['n']*abs(b['meanPredicted']-b['observed']) for b in bins)/len(events),'bins':bins}
    perstat=defaultdict(list);positions=defaultdict(list);game_types=defaultdict(list)
    for r in rows:
        game_types[r['gameType']].extend(p['error'] for p in r['score'])
        for p in r['player']:perstat[p['stat']].append(p);positions[p['position']].append(p['error'])
    return {'games':len(rows),'scores':means([p['error'] for r in rows for p in r['score']]),
            'baselineScores':means([e for r in rows for e in r['baselineScoreErrors']]),
            'total':means([r['total']['error'] for r in rows]),'margin':means([r['margin']['error'] for r in rows]),
            'scoreCRPS':float(np.mean([p['crps'] for r in rows for p in r['score']])),
            'homeWin':reliability([{'p':r['homeProbability'],'y':r['actualHomeWin']} for r in rows if not r['tie']]),
            'researchThresholds':reliability([{'p':p['rawProbability'],'y':p['outcome']} for r in rows for p in r['events']]),
            'teamThresholds':reliability([{'p':p['rawProbability'],'y':p['outcome']} for r in rows for p in r['teamEvents']]),
            'jointThresholds':reliability([{'p':p['rawProbability'],'y':p['outcome']} for r in rows for p in r['jointEvents']]),
            'players':{s:{**means([p['error'] for p in ps]),'observations':len(ps),'crps':float(np.mean([p['crps'] for p in ps])),
                          'coverage':{k:float(np.mean([p['coverage'][k]['covered'] for p in ps])) for k in ('0.5','0.8','0.9','0.95')}} for s,ps in perstat.items()},
            'positions':{k:means(v) for k,v in positions.items()},'gameTypes':{k:means(v) for k,v in game_types.items()},
            'qualityFlaggedGames':sum(bool(r['qualityFlags']) for r in rows),
            'scoreIntervalCoverage':{k:float(np.mean([p['coverage'][k]['covered'] for r in rows for p in r['score']])) for k in ('0.5','0.8','0.9','0.95')}}


def paired_gate(incumbent,challenger,max_candidates=3,replicates=2000):
    """Calendar-week paired bootstrap with multiplicity correction and vetoes.

    Selection objective is score CRPS; MAE, Brier, log-loss, CDF Brier and
    coverage are noninferiority vetoes. Multiple disjoint validation cohorts
    must improve; one lucky game or one good metric cannot promote a model.
    """
    a={r['gameId']:r for r in incumbent};b={r['gameId']:r for r in challenger}
    if a.keys()!=b.keys() or len(a)<24:return {'passed':False,'reason':'Insufficient identical paired games (minimum 24)','pairedGames':len(a.keys()&b.keys())}
    ids=sorted(a);groups=defaultdict(list);cohorts=defaultdict(list)
    for gid in ids:
        delta=np.mean([p['crps'] for p in b[gid]['score']])-np.mean([p['crps'] for p in a[gid]['score']])
        week=datetime.fromisoformat(a[gid]['eventStart'].replace('Z','+00:00')).strftime('%G-%V')
        groups[week].append(float(delta));cohorts[a[gid]['cohort']].append(float(delta))
    sa,sb=summary(list(a.values())),summary(list(b.values()));blocks=list(groups.values());rng=np.random.default_rng(16001);boot=[]
    for _ in range(replicates):boot.append(float(np.mean([x for i in rng.integers(0,len(blocks),len(blocks)) for x in blocks[int(i)]])))
    alpha=.05/max_candidates;interval=np.quantile(boot,[alpha/2,1-alpha/2]).tolist()
    veto=[]
    if len(blocks)<6:veto.append('fewer_than_six_calendar_weeks')
    if len(cohorts)<3 or sum(np.mean(v)<0 for v in cohorts.values())<2:veto.append('insufficient_independent_cohort_improvement')
    if interval[1]>=0:veto.append('crps_improvement_not_statistically_credible')
    if sb['scores']['mae']>sa['scores']['mae']:veto.append('score_mae_regression')
    if sum(r['coverage']['matchedPlayers'] for r in b.values())<.98*sum(r['coverage']['matchedPlayers'] for r in a.values()):veto.append('player_identity_coverage_regression')
    for metric in ('brier','logLoss'):
        if sb['homeWin'][metric]>sa['homeWin'][metric]:veto.append('home_win_'+metric+'_regression')
    if sb['researchThresholds'] and sa['researchThresholds'] and sb['researchThresholds']['brier']>sa['researchThresholds']['brier']:veto.append('player_cdf_brier_regression')
    if sb['homeWin']['ece']>sa['homeWin']['ece']:veto.append('home_win_calibration_regression')
    for stat,metrics in sa['players'].items():
        new=sb['players'].get(stat)
        if new and metrics['observations']>=50 and new['observations']>=50 and new['mae']>max(metrics['mae']*1.1,metrics['mae']+.5):veto.append('player_category_regression:'+stat)
    if abs(sb['scoreIntervalCoverage']['0.9']-.9)>abs(sa['scoreIntervalCoverage']['0.9']-.9):veto.append('interval_coverage_regression')
    if sb['qualityFlaggedGames']:veto.append('unrealistic_simulation')
    return {'passed':not veto,'pairedGames':len(ids),'weeks':len(blocks),'cohortMeanCRPSDifferences':{k:float(np.mean(v)) for k,v in cohorts.items()},
            'meanCRPSDifference':float(np.mean([v for vs in groups.values() for v in vs])),
            'multiplicityAdjustedCRPSInterval':interval,'familywiseAlpha':.05,'candidates':max_candidates,'vetoes':veto,
            'productionEligible':False,'productionReason':'Original historical availability, lineup and injury archives are incomplete; research selection is not production promotion.'}


def stop_reason(iterations,nonimproving,cpu_seconds,wall_seconds,limits):
    if cpu_seconds>=limits['cpuSeconds']:return 'cpu_budget_exhausted'
    if wall_seconds>=limits['wallSeconds']:return 'wall_budget_exhausted'
    if nonimproving>=limits['patience']:return 'validation_improvement_plateau'
    if iterations>=limits['maxIterations']:return 'predeclared_candidate_budget_exhausted'
    return None
