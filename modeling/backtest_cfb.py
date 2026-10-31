"""Event-chronological reconstruction of actual public CFB games.

Publication availability is unknown. This is a retrospective diagnostic, not a
prospective backtest, calibration approval or a market-edge claim.
"""
import argparse
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path

from .cfb_public_research import normalize_public_cfb, source_file
from .cfb_simulator import fit_cfb_csv, simulate_cfb, MODEL_VERSION, ENGINE_VERSION
from .fit import utc


def backtest_cfb_source(path, season, limit=4, simulations=10000):
    import pyarrow.parquet as pq
    import pyarrow.compute as pc
    table=pq.read_table(path,columns=['game_id','homeTeamId','awayTeamId','homeTeamName','awayTeamName',
                                     'homeFinalScore','awayFinalScore','wallclock','status_type_completed'])
    table=table.filter(pc.equal(table['status_type_completed'],True))
    games={}
    for row in table.to_pylist():
        if not row['wallclock'] or row['homeFinalScore'] is None or row['awayFinalScore'] is None:continue
        try:played=utc(row['wallclock'])
        except ValueError:continue
        if played>=datetime.now(timezone.utc):continue
        game=games.setdefault(str(row['game_id']),{**row,'firstObservedAt':played.isoformat()})
        if played<utc(game['firstObservedAt']):game['firstObservedAt']=played.isoformat()
    del table
    selected=sorted(games.values(),key=lambda game:game['firstObservedAt'],reverse=True)[:limit]
    rows=[];errors=[]
    for game in selected:
        home,away=str(game['homeTeamId']),str(game['awayTeamId'])
        try:
            corpus=normalize_public_cfb(path,home,away,game['firstObservedAt'])
            if 'cfb:espn:'+str(game['game_id']) in corpus['historicalGameIds']:
                raise ValueError('Held-out game entered its historical fitting corpus')
            model=fit_cfb_csv(corpus['csv'],'SportsDataverse ESPN-derived public CFB historical corpus; retrospective availability unknown',
                              corpus['asOf'],100,{'recencyHalfLifeDays':90,'conditionalShrinkage':True})['model']
            result=simulate_cfb(model,'cfb:espn:'+home,'cfb:espn:'+away,simulations,202608,
                                game['firstObservedAt'])
            p=result['homeWinProbability'];actual=int(game['homeFinalScore']>game['awayFinalScore'])
            rows.append({'gameId':'cfb:espn:'+str(game['game_id']),'home':game['homeTeamName'],
                         'away':game['awayTeamName'],'eventTime':game['firstObservedAt'],
                         'eventTimeMeaning':'First observed source play; not represented as an official scheduled kickoff.',
                         'trainingThrough':model['asOf'],'sourceInputVersion':model['sha256'],
                         'trainingGames':result['evidence']['games'],'trainingPlays':result['evidence']['plays'],
                         'simulations':simulations,'predictedHomeWinProbability':p,
                         'actualHomeWin':actual,'actualScore':[game['homeFinalScore'],game['awayFinalScore']],
                         'predictedScore':[result['scoreDistributions']['cfb:espn:'+home]['mean'],result['scoreDistributions']['cfb:espn:'+away]['mean']],
                         'brier':(p-actual)**2,
                         'logLoss':-actual*math.log(max(1e-12,p))-(1-actual)*math.log(max(1e-12,1-p)),
                         'heldOutGameExcluded':True})
        except (ValueError,KeyError,TypeError) as error:
            errors.append({'gameId':'cfb:espn:'+str(game['game_id']),'reason':str(error)})
    n=len(rows)
    return {'checkedAt':datetime.now(timezone.utc).isoformat(),'sport':'CFB','season':season,
            'status':'completed_retrospective_not_promoted','modelVersion':MODEL_VERSION,'engineVersion':ENGINE_VERSION,
            'sourceUrl':f'https://github.com/sportsdataverse/sportsdataverse-data/releases/download/espn_cfb_pbp/play_by_play_{season}.parquet',
            'sourceSha256':hashlib.sha256(Path(path).read_bytes()).hexdigest(),
            'selection':'The latest completed source games by first observed play time, selected before inspecting model errors; insufficient cohorts are retained as failures.',
            'requestedGames':limit,'evaluatedGames':n,'predictions':rows,'unavailableGames':errors,
            'brierScore':sum(row['brier'] for row in rows)/n if n else None,
            'logLoss':sum(row['logLoss'] for row in rows)/n if n else None,
            'marketBenchmark':None,'publicationAvailabilityVerified':False,'calibrationApproved':False,'promoted':False,
            'limitations':['Retrospectively retrieved/correctable source: event-chronological cutoff does not prove historical publication availability.',
                           'Small pilot sample cannot establish calibration, stable accuracy, economic value or superiority over market prices.',
                           'Current roster, injuries, transfers, weather and independent talent/strength-of-schedule effects are incompletely modeled.',
                           'No historical market-price series was available; no market comparison is invented.']}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--season',type=int,required=True)
    parser.add_argument('--games',type=int,default=4);parser.add_argument('--source-file')
    parser.add_argument('--output',required=True);args=parser.parse_args()
    if not 1<=args.games<=20:raise ValueError('Choose 1..20 audit games')
    source=args.source_file or source_file(args.season)['path']
    result=backtest_cfb_source(source,args.season,args.games)
    Path(args.output).write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({key:result[key] for key in ('status','evaluatedGames','brierScore','logLoss','promoted')}))


if __name__=='__main__':main()
