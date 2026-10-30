"""Chronological NFL home-win model suite with safe JSON artifacts.

Independent models never consume market prices. Historical closing moneylines are
an explicitly unverified-timing benchmark, not a DraftKings Predictions feed.
"""
import argparse
import csv
import hashlib
import io
import json
import math
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
from scipy.optimize import minimize
from scipy.special import expit, logit
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression

VERSION = 'nfl-home-win-suite-4.0.0'
FEATURES = ['strength_difference', 'margin_difference', 'home_offense', 'home_opponent_defense',
            'away_offense', 'away_opponent_defense', 'home_recent_win_rate', 'away_recent_win_rate',
            'home_sample_log', 'away_sample_log', 'home_field', 'rest_difference', 'divisional']
ALIASES = {'OAK': 'LV', 'SD': 'LAC', 'STL': 'LA', 'LAR': 'LA'}


def utc(value):
    parsed = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('Timezone-aware timestamps required')
    return parsed.astimezone(timezone.utc)


def finite(value, default=None):
    try:
        result = float(value)
        return result if math.isfinite(result) else default
    except (TypeError, ValueError):
        return default


def parse_games(raw, source, as_of):
    if not isinstance(raw, str) or len(raw.encode()) > 15_000_000 or not source or len(source) > 2000:
        raise ValueError('Real game-history CSV (max15MB) and source provenance required')
    cutoff = utc(as_of)
    if cutoff > datetime.now(timezone.utc):
        raise ValueError('asOf cannot be in the future')
    reader = csv.DictReader(io.StringIO(raw))
    required = {'game_id', 'season', 'week', 'gameday', 'home_team', 'away_team', 'home_score', 'away_score'}
    if not required.issubset(reader.fieldnames or []):
        raise ValueError('Missing historical game columns: '+', '.join(sorted(required-set(reader.fieldnames or []))))
    rows, seen = [], set()
    for r in reader:
        if r.get('game_type', 'REG') != 'REG':
            continue
        hs, aws = finite(r.get('home_score')), finite(r.get('away_score'))
        if hs is None or aws is None:
            continue
        date = datetime.fromisoformat(r['gameday']).replace(tzinfo=timezone.utc)
        # Conservative eligibility assumption: two UTC calendar days after the
        # schedule date. This is NOT invented source publication metadata.
        supplied = r.get('available_at')
        available = utc(supplied) if supplied else date+timedelta(days=2)
        if available >= cutoff:
            continue
        if min(hs, aws) < 0 or max(hs, aws) > 100 or hs != int(hs) or aws != int(aws):
            raise ValueError('Invalid historical final score')
        if available < date:
            raise ValueError('Outcome availability cannot precede the game date')
        if r['game_id'] in seen:
            raise ValueError('Duplicate game ID')
        seen.add(r['game_id'])
        home, away = ALIASES.get(r['home_team'], r['home_team']), ALIASES.get(r['away_team'], r['away_team'])
        if home == away or not home or not away:
            raise ValueError('Distinct known team identifiers required')
        row = {'id': r['game_id'], 'season': int(r['season']), 'week': int(r['week']), 'date': date.isoformat(),
               'eligibilityAt': available.isoformat(), 'sourceAvailableAt': available.isoformat() if supplied else None, 'availabilityVerified': bool(supplied), 'home': home, 'away': away,
               'homeScore': hs, 'awayScore': aws, 'homeField': float(r.get('location') != 'Neutral'),
               'restDiff': (finite(r.get('home_rest'), 7)-finite(r.get('away_rest'), 7)),
               'restMissing': not bool(r.get('home_rest') and r.get('away_rest')), 'division': finite(r.get('div_game'), 0),
               'marketProbability': None}
        hm, am = finite(r.get('home_moneyline')), finite(r.get('away_moneyline'))
        if hm is not None and am is not None and abs(hm) >= 100 and abs(am) >= 100:
            implied = lambda odd: 100/(100+odd) if odd > 0 else -odd/(100-odd)
            ph, pa = implied(hm), implied(am)
            row['marketProbability'] = ph/(ph+pa)
        rows.append(row)
    rows.sort(key=lambda r: (r['date'], r['id']))
    if len(rows) < 500:
        raise ValueError('At least500 completed historical games are required for model development')
    return rows, {'source': source, 'asOf': cutoff.isoformat(), 'modelIngestedAt':datetime.now(timezone.utc).isoformat(),'datasetSha256': hashlib.sha256(raw.encode()).hexdigest(),
                  'games': len(rows), 'availabilityVerified': all(r['availabilityVerified'] for r in rows),
                  'availabilityPolicy': 'Explicit available_at when provided; otherwise conservative game-date+2days assumption, not verified publication time.',
                  'reliability': 'historical_source_supplied; source revisions and quote timestamps not independently verified'}


class FeatureState:
    def __init__(self):
        self.history = defaultdict(list)
        self.pending = []
        self.applied = set()
        self.strength = defaultdict(float)

    def advance(self, before):
        eligible = sorted((r for r in self.pending if r['id'] not in self.applied and r['eligibilityAt'] < before), key=lambda r: (r['eligibilityAt'], r['id']))
        alpha = 1-math.exp(math.log(.5)/6)  # Explicit six-game recency half-life.
        for r in eligible:
            h, a, margin = r['home'], r['away'], r['homeScore']-r['awayScore']
            prior_h, prior_a = self.strength[h], self.strength[a]
            self.strength[h] = (1-alpha)*prior_h+alpha*(margin+prior_a)
            self.strength[a] = (1-alpha)*prior_a+alpha*(-margin+prior_h)
            self.history[h].append((r['homeScore'], r['awayScore'], margin, float(margin > 0)))
            self.history[a].append((r['awayScore'], r['homeScore'], -margin, float(margin < 0)))
            self.applied.add(r['id'])

    def vector(self, row):
        def summary(team):
            history = self.history[team][-24:]
            if not history:
                return np.zeros(4), 0
            weights = np.exp(np.arange(len(history))*math.log(2)/6)
            # Shrink sparse team estimates toward the actual available league
            # population instead of inventing an NFL league scoring constant.
            population = [v for records in self.history.values() for v in records[-24:]]
            league = np.mean(population, axis=0) if population else np.zeros(4)
            value = np.average(history, axis=0, weights=weights)
            return (len(history)*value+8*league)/(len(history)+8), len(history)
        h, hn = summary(row['home']); a, an = summary(row['away'])
        return [self.strength[row['home']]-self.strength[row['away']], h[2]-a[2], h[0], a[1], a[0], h[1], h[3], a[3],
                math.log1p(hn), math.log1p(an), row['homeField'], max(-21, min(21, row['restDiff'])), row['division']]


def design(rows):
    state, vectors = FeatureState(), []
    for r in rows:
        state.advance(r['date'])
        vectors.append(state.vector(r))
        state.pending.append(r)
    return np.asarray(vectors, dtype=float)


def standardize(x, mean=None, scale=None):
    mean = np.mean(x, axis=0) if mean is None else np.asarray(mean)
    scale = np.std(x, axis=0) if scale is None else np.asarray(scale)
    scale = np.where(scale < 1e-8, 1, scale)
    return (x-mean)/scale, mean, scale


def team_design(x, rows, teams):
    out = np.zeros((len(rows), len(teams)))
    index = {team: i for i, team in enumerate(teams)}
    for i, row in enumerate(rows):
        if row['home'] in index: out[i,index[row['home']]] = 1
        if row['away'] in index: out[i,index[row['away']]] = -1
    return np.column_stack([np.ones(len(rows)), out, x])


def recency_weights(rows):
    end = max(utc(r['date']) for r in rows)
    return np.asarray([math.exp(-math.log(2)*(end-utc(r['date'])).days/730) for r in rows])


def fit_bayesian(x, rows, scale):
    teams = sorted(set(r['home'] for r in rows)|set(r['away'] for r in rows))
    z, mean, std = standardize(x)
    a = team_design(z, rows, teams)
    y = np.asarray([float(r['homeScore'] > r['awayScore']) for r in rows])
    weights = recency_weights(rows)
    precision = np.ones(a.shape[1]); precision[0] = .01; precision[1:len(teams)+1] = 1/scale**2
    def objective(b):
        eta = a@b
        return float(np.sum(weights*(np.logaddexp(0,eta)-y*eta))+.5*np.sum(precision*b*b)), a.T@(weights*(expit(eta)-y))+precision*b
    result = minimize(objective, np.zeros(a.shape[1]), jac=True, method='L-BFGS-B', options={'maxiter':300, 'ftol':1e-10})
    if not result.success and np.max(np.abs(result.jac)) > .05:
        raise ValueError('Bayesian MAP optimizer failed to converge')
    p = expit(a@result.x)
    hessian = (a.T*(weights*p*(1-p)))@a+np.diag(precision)
    covariance = np.linalg.pinv(hessian)
    return {'kind':'bayesian_team_strength_laplace','teams':teams,'mean':mean.tolist(),'scale':std.tolist(),'coefficients':result.x.tolist(),
            'covariance':covariance.tolist(),'teamPriorSD':scale,'posteriorMethod':'Gaussian team random-effect prior with chronology-selected shared scale; MAP/Laplace approximation, not full MCMC'}


def fit_regularized(x, rows, c):
    z, mean, std = standardize(x)
    model = LogisticRegression(C=c, max_iter=500, random_state=42).fit(z, [int(r['homeScore'] > r['awayScore']) for r in rows], sample_weight=recency_weights(rows))
    return {'kind':'regularized_recency_team_features','mean':mean.tolist(),'scale':std.tolist(),'coefficients':model.coef_[0].tolist(),'intercept':float(model.intercept_[0]),'C':c}


def fit_boosting(x, rows, depth):
    model = GradientBoostingClassifier(n_estimators=80,learning_rate=.05,max_depth=depth,min_samples_leaf=25,random_state=42).fit(x,[int(r['homeScore'] > r['awayScore']) for r in rows],sample_weight=recency_weights(rows))
    trees=[]
    for estimator in model.estimators_[:,0]:
        t=estimator.tree_
        trees.append({'left':t.children_left.tolist(),'right':t.children_right.tolist(),'feature':t.feature.tolist(),'threshold':t.threshold.tolist(),'value':t.value[:,0,0].tolist()})
    prior = model.init_.class_prior_[1]
    return {'kind':'gradient_boosted_game_features','baseLogit':float(logit(prior)),'learningRate':.05,'trees':trees,'maxDepth':depth}


def predict_model(model, x, rows, interval=False):
    x=np.asarray(x,dtype=float)
    if model['kind']=='bayesian_team_strength_laplace':
        z,_,_=standardize(x,model['mean'],model['scale']); a=team_design(z,rows,model['teams']); eta=a@np.asarray(model['coefficients']); p=expit(eta)
        if interval:
            cov=np.asarray(model['covariance']); se=np.sqrt(np.maximum(0,np.einsum('ij,jk,ik->i',a,cov,a)))
            return p,np.column_stack([expit(eta-1.96*se),expit(eta+1.96*se)])
        return p
    if model['kind']=='regularized_recency_team_features':
        z,_,_=standardize(x,model['mean'],model['scale']);return expit(model['intercept']+z@np.asarray(model['coefficients']))
    if model['kind']!='gradient_boosted_game_features':raise ValueError('Unknown model kind')
    score=np.full(len(x),model['baseLogit'],dtype=float)
    for tree in model['trees']:
        left,right,feature,threshold,value=(tree[k] for k in ['left','right','feature','threshold','value'])
        for i,row in enumerate(x):
            node=0
            while left[node]!=-1:
                node=left[node] if row[feature[node]]<=threshold[node] else right[node]
            score[i]+=model['learningRate']*value[node]
    return expit(score)


def scores(p,y):
    p=np.clip(np.asarray(p,dtype=float),1e-9,1-1e-9);y=np.asarray(y,dtype=float)
    return {'n':len(y),'brier':float(np.mean((p-y)**2)),'logLoss':float(np.mean(-y*np.log(p)-(1-y)*np.log(1-p))),
            'accuracy':float(np.mean((p>=.5)==y))}


def platt_fit(p,y):
    x=logit(np.clip(p,1e-6,1-1e-6)).reshape(-1,1)
    model=LogisticRegression(C=1,max_iter=300).fit(x,y)
    return {'slope':float(model.coef_[0,0]),'intercept':float(model.intercept_[0])}


def calibrate(p,cal):
    return expit(cal['intercept']+cal['slope']*logit(np.clip(p,1e-9,1-1e-9)))


def ensemble_fit(probabilities,y):
    matrix=np.column_stack(probabilities);y=np.asarray(y)
    def objective(w):
        p=np.clip(matrix@w,1e-9,1-1e-9)
        return float(np.mean(-y*np.log(p)-(1-y)*np.log(1-p))+.02*np.sum((w-1/len(w))**2))
    fitted=minimize(objective,np.full(matrix.shape[1],1/matrix.shape[1]),bounds=[(0,1)]*matrix.shape[1],constraints=[{'type':'eq','fun':lambda w:sum(w)-1}],method='SLSQP')
    if not fitted.success:raise ValueError('Ensemble optimizer failed')
    return fitted.x/fitted.x.sum()


def block_interval(values,groups,seed=42,repeats=1000):
    values=np.asarray(values,dtype=float);unique=sorted(set(groups));mapping={k:np.flatnonzero(np.asarray(groups)==k) for k in unique};rng=np.random.default_rng(seed)
    if len(unique)<8:return None
    results=[]
    for _ in range(repeats):
        indexes=np.concatenate([mapping[k] for k in rng.choice(unique,size=len(unique),replace=True)])
        results.append(float(np.mean(values[indexes])))
    return [float(x) for x in np.quantile(results,[.025,.975])]


def calibration_table(p,y):
    out=[];buckets=np.minimum(9,np.floor(np.asarray(p)*10).astype(int))
    for i in range(10):
        mask=buckets==i
        if np.any(mask):out.append({'from':i/10,'to':(i+1)/10,'n':int(mask.sum()),'predicted':float(np.mean(p[mask])),'observed':float(np.mean(y[mask]))})
    if sum(b['n'] for b in out)!=len(p):raise ValueError('Calibration buckets do not reconcile with validation sample')
    return out


def feature_drift(reference,recent):
    """PSI is a diagnostic shift measure, never a calibrated failure probability."""
    result=[]
    for column,name in enumerate(FEATURES):
        edges=np.unique(np.quantile(reference[:,column],np.linspace(0,1,11)))
        if len(edges)<3:continue
        edges[0],edges[-1]=-np.inf,np.inf
        a=np.histogram(reference[:,column],edges)[0]+.5;b=np.histogram(recent[:,column],edges)[0]+.5
        a,b=a/a.sum(),b/b.sum();psi=float(np.sum((b-a)*np.log(b/a)))
        result.append({'feature':name,'psi':psi,'attention':psi>.25})
    return {'metrics':result,'recentGames':len(recent),'referenceGames':len(reference),'method':'Training-quantile population stability index with half-count smoothing.0.25 is a declared diagnostic heuristic, not proof of predictive drift.'}


def fit_protocol(rows,x,season,first_season):
    early=[i for i,r in enumerate(rows) if first_season<=r['season']<=season-3]
    tuning=[i for i,r in enumerate(rows) if r['season']==season-2]
    train=early+tuning;cal=[i for i,r in enumerate(rows) if r['season']==season-1]
    if min(len(early),len(tuning),len(cal))<100:raise ValueError(f'Insufficient chronology for targetseason{season}')
    subset=lambda ids:[rows[i] for i in ids]
    y=lambda ids:np.asarray([int(rows[i]['homeScore']>rows[i]['awayScore']) for i in ids])
    models,choices={},{}
    for name,options,fit in [('bayesian',[.5,1.0],fit_bayesian),('regularized',[.1,1.0],fit_regularized),('boosting',[1,2],fit_boosting)]:
        candidates=[]
        for option in options:
            candidate=fit(x[early],subset(early),option)
            candidates.append((scores(predict_model(candidate,x[tuning],subset(tuning)),y(tuning))['logLoss'],option))
        choices[name]=min(candidates)[1]
        models[name]=fit(x[train],subset(train),choices[name])
    cal_fit=[i for i in cal if rows[i]['week']<=9];stack_fit=[i for i in cal if rows[i]['week']>9]
    if min(len(cal_fit),len(stack_fit))<60:raise ValueError('Separate calibration/stacking partitions require60+games each')
    calibrators={};stack=[]
    for name,model in models.items():
        calibrators[name]=platt_fit(predict_model(model,x[cal_fit],subset(cal_fit)),y(cal_fit))
        stack.append(calibrate(predict_model(model,x[stack_fit],subset(stack_fit)),calibrators[name]))
    return {'early':early,'tuning':tuning,'train':train,'cal':cal,'calFit':cal_fit,'stackFit':stack_fit,'models':models,'choices':choices,'calibrators':calibrators,'weights':ensemble_fit(stack,y(stack_fit))}


def benchmark(raw,source,as_of,holdout_seasons=(2023,2024,2025),first_season=2014):
    rows,provenance=parse_games(raw,source,as_of);x=design(rows)
    if not holdout_seasons or len(holdout_seasons)>5:raise ValueError('Choose1–5 chronological heldout seasons')
    predictions=[];folds=[];last_artifact=None
    for season in sorted(set(int(s) for s in holdout_seasons)):
        fitted=fit_protocol(rows,x,season,first_season)
        early,tuning,train,cal,cal_fit,stack_fit=(fitted[k] for k in ['early','tuning','train','cal','calFit','stackFit'])
        test=[i for i,r in enumerate(rows) if r['season']==season]
        if len(test)<100:raise ValueError('At least100 untouched holdout games required')
        models,calibrators,weights,choices=(fitted[k] for k in ['models','calibrators','weights','choices'])
        subset=lambda ids:[rows[i] for i in ids]
        y=lambda ids:np.asarray([int(rows[i]['homeScore']>rows[i]['awayScore']) for i in ids])
        raw_predictions={name:predict_model(model,x[test],subset(test)) for name,model in models.items()}
        test_predictions={name:calibrate(raw_predictions[name],calibrators[name]) for name in models}
        combined=np.column_stack(list(test_predictions.values()))@weights
        baseline=(float(y(train).sum())+.5)/(len(train)+1)
        for j,index in enumerate(test):
            r=rows[index]
            predictions.append({'id':r['id'],'date':r['date'],'sourceAvailableAt':r['sourceAvailableAt'],'featureEligibilityAt':r['eligibilityAt'],'season':season,'week':r['week'],'home':r['home'],'away':r['away'],'outcome':int(y([index])[0]),'probabilities':{name:float(v[j]) for name,v in test_predictions.items()},'rawProbabilities':{name:float(v[j]) for name,v in raw_predictions.items()},'ensemble':float(combined[j]),'disagreement':float(max(v[j] for v in test_predictions.values())-min(v[j] for v in test_predictions.values())),'trainingHomeBaseline':baseline,'marketBenchmark':r['marketProbability']})
        folds.append({'holdoutSeason':season,'trainingGames':len(train),'trainingThroughSeason':season-2,'hyperparameterTuneSeason':season-2,'calibrationSeason':season-1,'calibrationGames':len(cal_fit),'ensembleWeightGames':len(stack_fit),'holdoutGames':len(test),'choices':choices,'ensembleWeights':{name:float(weights[i]) for i,name in enumerate(models)},'holdoutMetrics':scores(combined,y(test))})
        last_artifact={'version':VERSION,'asOf':as_of,'models':models,'calibrators':calibrators,'ensembleWeights':weights.tolist(),'modelOrder':list(models),'history':rows,'featureNames':FEATURES,'trainingThroughSeason':season-2,'calibrationSeason':season-1,'provenance':provenance}
    yy=np.asarray([r['outcome'] for r in predictions]);groups=[f"{r['season']}-{r['week']}" for r in predictions]
    metrics={};allp={name:np.asarray([r['probabilities'][name] for r in predictions]) for name in ['bayesian','regularized','boosting']}
    allp['ensemble']=np.asarray([r['ensemble'] for r in predictions]);allp['training_home_baseline']=np.asarray([r['trainingHomeBaseline'] for r in predictions]);allp['constant_50']=np.full(len(yy),.5)
    for name,p in allp.items():
        metrics[name]={**scores(p,yy),'brierWeekBlock95':block_interval((p-yy)**2,groups),'calibration':calibration_table(p,yy)}
        if name in ('bayesian','regularized','boosting'):
            raw=np.asarray([r['rawProbabilities'][name] for r in predictions]);metrics[name]['uncalibrated']=scores(raw,yy)
    ensemble=allp['ensemble'];reference=allp['training_home_baseline'];difference=(ensemble-yy)**2-(reference-yy)**2
    paired=block_interval(difference,groups);loss_diff=(-yy*np.log(ensemble)-(1-yy)*np.log(1-ensemble))-(-yy*np.log(reference)-(1-yy)*np.log(1-reference));log_ci=block_interval(loss_diff,groups)
    market_mask=np.asarray([r['marketBenchmark'] is not None for r in predictions]);market_comparison=None
    if market_mask.any():
        mp=np.asarray([r['marketBenchmark'] or .5 for r in predictions]);market_comparison={'n':int(market_mask.sum()),'modelOnCommonGames':scores(ensemble[market_mask],yy[market_mask]),'marketOnCommonGames':scores(mp[market_mask],yy[market_mask]),'pairedBrierDifference95':block_interval(((ensemble-yy)**2-(mp-yy)**2)[market_mask],np.asarray(groups)[market_mask].tolist()),'timingVerified':False,'exactSettlementCompatible':False,'sourceMeaning':'Indicative source historical home/away moneylines normalized to remove two-sided overround. Moneyline tie/push terms and quote times are unverified; not exact DK Predictions binary settlement or executable prices.'}
    research_pass=len(yy)>=500 and len(folds)>=2 and paired is not None and paired[1]<0 and log_ci is not None and log_ci[1]<0
    report={'version':VERSION,'provenance':provenance,'n':len(yy),'folds':folds,'metrics':metrics,'pairedBrierDifferenceVsHomeBaseline95':paired,'pairedLogLossDifferenceVsHomeBaseline95':log_ci,'marketComparison':market_comparison,'promotion':{'researchGatePassed':bool(research_pass),'productionEligible':False,'status':'research_only','reasons':['Historical source availability/revisions and market quote timing are not independently verified.','Validation is for home-win game outcomes only; does not validate player props or fitted play-by-play distributions.','No automated production promotion; report prospective monitoring and complete uncertainty first.']},'validation':'Nested chronological tuning, separate early/late calibration-year partitions for Platt and stacking, rolling annual untouched holdouts; no market features in independent models.','predictionTarget':'Home win YES; ties are NO. No claim about away-win conditional probability.','predictions':predictions,'createdAt':datetime.now(timezone.utc).isoformat(),'limitations':['No injury, roster, player, weather or play-by-play features are inferred from absent sources.','Recency half-lives and shrinkage priors are declared modeling choices; model parameters and tuning choices are data-fitted.','Laplace uncertainty conditions on the model family and fitted hyperparameter; not all structural uncertainty.','Week-block bootstrap addresses some within-week dependence, not all nonstationarity.']}
    complete=[season for season in sorted(set(r['season'] for r in rows)) if sum(r['season']==season for r in rows)>=250]
    live_year=max(complete)+1
    if live_year>last_artifact['calibrationSeason']+1:
        latest=fit_protocol(rows,x,live_year,first_season)
        last_artifact.update(models=latest['models'],calibrators=latest['calibrators'],ensembleWeights=latest['weights'].tolist(),modelOrder=list(latest['models']),trainingThroughSeason=live_year-2,calibrationSeason=live_year-1)
    reference=np.asarray([i for i,r in enumerate(rows) if first_season<=r['season']<=last_artifact['trainingThroughSeason']])
    report['featureDrift']=feature_drift(x[reference],x[-100:])
    report['ensembleComponentComparison']={name:{'pairedBrierDifference95':block_interval((ensemble-yy)**2-(p-yy)**2,groups),'scope':'Descriptive paired holdout comparison; no assumption an ensemble improves every component.'} for name,p in allp.items() if name in ('bayesian','regularized','boosting')}
    last_artifact['validation']={k:v for k,v in report.items() if k not in ('predictions','metrics','marketComparison')}
    last_artifact['validation']['liveRefit']={'trainingThroughSeason':last_artifact['trainingThroughSeason'],'calibrationSeason':last_artifact['calibrationSeason'],'policy':'Identical chronology/tuning protocol refitted after validation; still research only, never promoted automatically.'}
    report['modelVersion']=VERSION;last_artifact['modelVersion']=VERSION
    return {'report':report,'model':last_artifact,'modelVersion':VERSION,'summary':{'modelVersion':VERSION,'heldoutGames':report['n'],'brier':report['metrics']['ensemble']['brier'],'logLoss':report['metrics']['ensemble']['logLoss'],'productionEligible':False,'provenance':provenance}}


def predict(artifact,home,away,event_start,rest_difference=None,division=False):
    if artifact.get('version')!=VERSION:raise ValueError('A fitted JSON game-model artifact is required')
    event=utc(event_start)
    if event<=utc(artifact['asOf']):raise ValueError('Event must be after artifact evidence cutoff')
    home,away=ALIASES.get(home,home),ALIASES.get(away,away)
    if home==away:raise ValueError('Distinct teams required')
    known=set(r['home'] for r in artifact['history'])|set(r['away'] for r in artifact['history'])
    if home not in known or away not in known:raise ValueError('Unknown team: insufficient training history')
    row={'home':home,'away':away,'date':event.isoformat(),'homeField':1.,'restDiff':finite(rest_difference,0),'division':float(bool(division))}
    state=FeatureState();state.pending=artifact['history'];state.advance(event.isoformat());x=np.asarray([state.vector(row)])
    outputs={};interval=None
    for name in artifact['modelOrder']:
        model=artifact['models'][name]
        if name=='bayesian':
            raw,ci=predict_model(model,x,[row],True);cal=artifact['calibrators'][name];interval=[float(v) for v in calibrate(ci[0],cal)]
            interval=sorted(interval)
        else:raw=predict_model(model,x,[row])
        outputs[name]=float(calibrate(raw,artifact['calibrators'][name])[0])
    p=float(np.dot(artifact['ensembleWeights'],[outputs[name] for name in artifact['modelOrder']]))
    return {'version':VERSION,'modelVersion':VERSION,'home':home,'away':away,'eventStart':event.isoformat(),'homeWinProbability':p,'models':outputs,'disagreementRange':[min(outputs.values()),max(outputs.values())],'bayesianParameterInterval95':interval,'ensembleParameterInterval':None,'evidenceCutoff':artifact['asOf'],'trainingThroughSeason':artifact['trainingThroughSeason'],'calibrationSeason':artifact['calibrationSeason'],'productionEligible':False,'uncertainty':'Bayesian interval is a conditional Laplace parameter interval after calibration; ensemble structural uncertainty is not estimated.','target':'Home-win YES (ties NO)','features':dict(zip(FEATURES,[float(v) for v in x[0]])),'inputAssumptions':{'restDifference':rest_difference,'restMissingDefault':rest_difference is None,'homeField':True,'division':bool(division)},'createdAt':datetime.now(timezone.utc).isoformat()}


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('csv');parser.add_argument('--source',required=True);parser.add_argument('--as-of',required=True);parser.add_argument('--seasons',default='2023,2024,2025');parser.add_argument('--out',required=True);parser.add_argument('--model-out');args=parser.parse_args()
    result=benchmark(Path(args.csv).read_text(),args.source,args.as_of,tuple(int(x) for x in args.seasons.split(',')))
    Path(args.out).parent.mkdir(parents=True,exist_ok=True);Path(args.out).write_text(json.dumps(result['report'],indent=2)+'\n')
    if args.model_out:Path(args.model_out).write_text(json.dumps(result['model'])+'\n')
    print(json.dumps({'n':result['report']['n'],'ensemble':result['report']['metrics']['ensemble'],'promotion':result['report']['promotion']}))

if __name__=='__main__':main()
