"""Predeclared fixed-cutoff game-market audit on actual nflverse play-by-play.

Research thresholds are not claimed to be historical exchange contracts/prices.
Unknown historical first-publication times prevent prospective promotion.
"""
import argparse
from collections import defaultdict
from datetime import datetime,timezone
import hashlib
import json
import math
from pathlib import Path
import random

from .backtest_player_props import select_holdout_games
from .fit import fit_csv,utc
from .game_research import evaluate_exact_game_distribution
from .nflverse_adapter import normalize,number,read_pbp,SOURCE
from .simulator import simulate

PROTOCOL='retrospective-predeclared-game-markets-7.0.0'
FIXED_DEFINITIONS=(
    {'id':'home_winner','kind':'home_win','equality':'no'},
    {'id':'home_margin_above_3_5','kind':'spread','threshold':3.5,'direction':'over','equality':'no'},
    {'id':'total_above_44_5','kind':'total','threshold':44.5,'direction':'over','equality':'no'},
    {'id':'home_total_above_20_5','kind':'team_total','team':'home','threshold':20.5,'direction':'over','equality':'no'},
    {'id':'away_total_above_20_5','kind':'team_total','team':'away','threshold':20.5,'direction':'over','equality':'no'},
)


def verified_final_scores(rows,game):
    selected=[row for row in rows if row.get('game_id')==game['id']]
    if not selected or not any(str(row.get('desc','')).strip().upper()=='END GAME' for row in selected):
        raise ValueError('A recorded END GAME marker is required; unfinished scores are unavailable')
    scores=[]
    for column in ('home_score','away_score'):
        observed={row[column] for row in selected if row.get(column) not in (None,'','NA','NaN')}
        if len(observed)!=1:raise ValueError('Final game scores are absent or internally inconsistent')
        value=float(next(iter(observed)))
        if not math.isfinite(value) or value<0 or int(value)!=value:
            raise ValueError('An actual nonnegative integer final score is required')
        scores.append(int(value))
    return scores


def observed_outcome(definition,scores):
    kind=definition['kind']
    if kind=='home_win':return int(scores[0]>scores[1])
    if kind=='spread':value=scores[0]-scores[1]
    elif kind=='total':value=sum(scores)
    elif kind=='team_total':value=scores[0 if definition['team']=='home' else 1]
    else:raise ValueError('Unsupported fixed audit definition')
    if value==definition['threshold']:raise ValueError('A fixed noninteger research threshold unexpectedly produced an equality')
    return int(value>definition['threshold'])


def game_block_interval(observations,seed=20261031,replicates=1000):
    grouped=defaultdict(list)
    for row in observations:grouped[row['gameId']].append(row)
    if len(grouped)<2:return None
    keys=sorted(grouped);rng=random.Random(seed);values=[]
    for _ in range(replicates):
        chosen=[row for _ in keys for row in grouped[rng.choice(keys)]]
        values.append(sum(row['brier'] for row in chosen)/len(chosen))
    values.sort()
    return[values[int(.025*replicates)],values[math.ceil(.975*replicates)-1]]


def audit(path,train_week=6,heldout_week=7,limit=4,simulations=10000):
    if simulations not in (10000,50000,100000):raise ValueError('Use10,000,50,000 or100,000 coherent complete games')
    raw=Path(path).read_bytes();rows=read_pbp(path)
    games=select_holdout_games(rows,train_week,heldout_week,limit)
    cutoff=min(game['eventStart'] for game in games)[:10]+'T00:00:00Z'
    if utc(cutoff)>=datetime.now(timezone.utc):raise ValueError('The fixed heldout games must be historical')
    training=[row for row in rows if row.get('season_type')=='REG' and number(row,'week')<=train_week]
    csv,conversion=normalize(training,train_week)
    model=fit_csv(csv,SOURCE+'; retrospective historical first-publication unverified',cutoff,options={'conditionalShrinkage':True,'recencyHalfLifeDays':90})['model']
    if any(utc(row['at'])>=utc(cutoff) for row in model['rows']):raise ValueError('Look-ahead detected in the fixed training prefix')
    observations=[];reports=[]
    definitions=[{**definition,'period':'full_game_including_overtime'} for definition in FIXED_DEFINITIONS]
    for game in games:
        result=simulate(model,game['home'],game['away'],simulations,20261031,game['eventStart'],definitions,
                        parameter_uncertainty={'replicates':10,'gamesPerReplicate':100})
        # Final outcomes are read only after the fixed definitions and model
        # outputs have been calculated; no score chooses a market or threshold.
        scores=verified_final_scores(rows,game)
        for definition in definitions:
            estimate=evaluate_exact_game_distribution(result,definition)
            p=estimate['rawSimulationProbability'];y=observed_outcome(definition,scores)
            clipped=max(1e-12,min(1-1e-12,p))
            observations.append({'gameId':game['id'],'category':definition['kind'],'definition':definition,
                                 'rawProbability':p,'calibratedProbability':None,'outcome':y,
                                 'brier':(p-y)**2,'logLoss':-y*math.log(clipped)-(1-y)*math.log(1-clipped),
                                 'monteCarloInterval95':estimate['monteCarloInterval95'],
                                 'parameterSensitivityInterval95':estimate['parameterInterval95'],
                                 'simulations':simulations,'retrospective':True})
        reports.append({**game,'actualHome':scores[0],'actualAway':scores[1],'simulations':simulations,
                        'scoreHistogramCounts':{team:sum(point['count'] for point in distribution['histogram']) for team,distribution in result['scoreDistributions'].items()},
                        'modelVersion':result['modelVersion'],'engineVersion':result['engineVersion'],
                        'parameterCompleteGames':result['uncertainty']['parameterBootstrap']['completeGames']})
    diagnostic=[]
    for bucket in range(10):
        selected=[row for row in observations if min(9,int(row['rawProbability']*10))==bucket]
        diagnostic.append({'from':bucket/10,'to':(bucket+1)/10,'n':len(selected),
                           'predicted':sum(row['rawProbability'] for row in selected)/len(selected) if selected else None,
                           'observed':sum(row['outcome'] for row in selected)/len(selected) if selected else None})
    return{'protocol':PROTOCOL,'status':'retrospective_research_only','createdAt':datetime.now(timezone.utc).isoformat(),
           'source':SOURCE,'datasetSha256':hashlib.sha256(raw).hexdigest(),'trainingThroughWeek':train_week,
           'heldoutWeek':heldout_week,'cutoff':cutoff,'trainingPlays':len(model['rows']),
           'trainingGames':len({row['game'] for row in model['rows']}),'n':len(observations),'independentGameBlocks':len(games),
           'selection':'First heldout games by recorded event time; all five predeclared research definitions evaluated for every game. No outcome-based market or threshold selection.',
           'definitions':definitions,'games':reports,'observations':observations,'calibrationDiagnostic':diagnostic,
           'brier':sum(row['brier'] for row in observations)/len(observations),
           'logLoss':sum(row['logLoss'] for row in observations)/len(observations),
           'brierGameBlockBootstrap95':game_block_interval(observations),'inputConversion':conversion,
           'calibratedProbabilitiesAvailable':False,'historicalFirstPublicationVerified':False,
           'productionEligible':False,'promotion':'NOT PROMOTED','marketBenchmark':None,
           'prospectiveSnapshotsCreated':0,'personalFinancialRecordsChanged':False,
           'limitations':['Small retrospective cohort with correlated within-game contracts; independent game-block count, not row count, determines evidence strength.',
                          'Current public historical files may include later revisions. Historical first-publication times are unknown; this cannot validate prospective deployment.',
                          'Research thresholds are predeclared examples, not fabricated DraftKings contracts or prices. Market benchmark, fees and profitability are unavailable.',
                          'Injury mixtures, numerical weather and future usage are not fully modeled. Parameter sensitivity excludes unestimated structural uncertainty.',
                          'Calibration diagnostics and game-block intervals on this small sample do not establish calibration or superiority.']}


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('input',type=Path)
    parser.add_argument('--train-week',type=int,default=6);parser.add_argument('--heldout-week',type=int,default=7)
    parser.add_argument('--games',type=int,default=4);parser.add_argument('--simulations',type=int,default=10000)
    parser.add_argument('--out',type=Path,required=True);args=parser.parse_args()
    report=audit(args.input,args.train_week,args.heldout_week,args.games,args.simulations)
    args.out.parent.mkdir(parents=True,exist_ok=True);args.out.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({key:report[key] for key in ('status','n','independentGameBlocks','brier','logLoss','promotion')}))


if __name__=='__main__':main()
