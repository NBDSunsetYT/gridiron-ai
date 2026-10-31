"""Fixed-cutoff, retrospective player-prop mechanics audit on public NFL data.

The threshold protocol and player-selection rule are fixed before inspecting
heldout outcomes. Historical first-publication times are unknown, so this audit
cannot approve a calibrator, claim prospective accuracy, or establish an edge.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path

from .fit import fit_csv
from .nflverse_adapter import normalize, number
from .public_research import fetch_dataset
from .simulator import simulate

PROTOCOL = 'retrospective-fixed-player-thresholds-6.0.0'
THRESHOLDS = (('passingYards', 'qb', 199.5), ('rushingYards', 'runner', 59.5), ('receivingYards', 'receiver', 40.5))
STAT_COLUMNS = {'passingYards':'passing_yards', 'rushingYards':'rushing_yards', 'receivingYards':'receiving_yards'}


def select_holdout_games(rows, train_week, heldout_week, limit):
    if not isinstance(limit, int) or not 1 <= limit <= 32 or not 1 <= train_week < heldout_week <= 18:
        raise ValueError('Use a fixed strictly later heldout week, and1..32 games.')
    games = {}
    for row in rows:
        if row.get('season_type') != 'REG' or number(row, 'week') != heldout_week:
            continue
        stamp = row.get('time_of_day')
        if not stamp:
            continue
        game_id = row.get('game_id')
        if not game_id:
            continue
        old = games.get(game_id)
        if old is None or stamp < old['eventStart']:
            games[game_id] = {'id':game_id, 'home':row.get('home_team'), 'away':row.get('away_team'), 'eventStart':stamp}
    selected = sorted(games.values(), key=lambda row:(row['eventStart'], row['id']))[:limit]
    if not selected or any(not row['home'] or not row['away'] for row in selected):
        raise ValueError('Actual recorded heldout game times and team identities are required; no schedule was invented.')
    return selected


def leading_training_players(model, team):
    selected = []
    for stat, identity_key, threshold in THRESHOLDS:
        counts = Counter(row[identity_key] for row in model['rows'] if row['o'] == team and row.get(identity_key))
        if counts:
            player_id = sorted(counts, key=lambda player:(-counts[player],player))[0]
            selected.append({'playerId':player_id, 'stat':stat, 'threshold':threshold, 'trainingOpportunities':counts[player_id]})
    return selected


def actual_row_value(rows, game, player_id, team, stat):
    matches = [row for row in rows if row.get('game_id') == game['id'] and row.get('player_id') == player_id and row.get('team') == team]
    if len(matches) != 1:
        return None
    row = matches[0]
    if not any(number(row, column) > 0 for column in ('attempts','targets','carries')):
        return None  # Missing/zero activity is not verified unrestricted participation.
    value = row.get(STAT_COLUMNS[stat])
    if value in (None,'','NA','NaN'):
        return None
    value = float(value)
    return int(value) if math.isfinite(value) and value.is_integer() else None


def audit(season=2026, train_week=6, heldout_week=7, limit=2, simulations=10000):
    if simulations not in (10000,50000,100000):
        raise ValueError('Use10,000,50,000 or100,000 complete games.')
    pbp = fetch_dataset('pbp',season)
    raw = list(pbp.rows())
    games = select_holdout_games(raw,train_week,heldout_week,limit)
    cutoff = min(game['eventStart'] for game in games)[:10]+'T00:00:00Z'
    if datetime.fromisoformat(cutoff.replace('Z','+00:00')) >= datetime.now(timezone.utc):
        raise ValueError('Historical validation must use completed past event periods.')
    training = [row for row in raw if row.get('season_type') == 'REG' and number(row,'week') <= train_week]
    text, conversion = normalize(training,train_week)
    fitted = fit_csv(text,pbp.metadata['url']+'; retrospective first-publication times unknown',cutoff,options={'conditionalShrinkage':True,'recencyHalfLifeDays':90})
    model = fitted['model']
    if any(datetime.fromisoformat(row['at']) >= datetime.fromisoformat(cutoff.replace('Z','+00:00')) for row in model['rows']):
        raise ValueError('A heldout/future event leaked into the fixed training prefix.')
    stats = fetch_dataset('player_stats',season)
    final_rows = [row for row in stats.rows() if row.get('season_type') == 'REG' and number(row,'week') == heldout_week]
    observations, excluded, game_results = [], [], []
    for game in games:
        definitions = []
        for team in (game['home'],game['away']):
            for candidate in leading_training_players(model,team):
                definitions.append({'id':f"{game['id']}:{team}:{candidate['stat']}", 'kind':'player', 'playerId':candidate['playerId'], 'stat':candidate['stat'], 'threshold':candidate['threshold'], 'direction':'over','equality':'no','team':team,'trainingOpportunities':candidate['trainingOpportunities']})
        # Extra audit metadata is stripped before engine validation. Every
        # selected player still emerges from the same complete game events.
        engine_contracts = [{key:value for key,value in definition.items() if key not in ('team','trainingOpportunities')} for definition in definitions]
        result = simulate(model,game['home'],game['away'],simulations,2026,game['eventStart'],contracts=engine_contracts)
        probabilities = {row['id']:row for row in result['contracts']}
        for definition in definitions:
            actual = actual_row_value(final_rows,game,definition['playerId'],definition['team'],definition['stat'])
            if actual is None:
                excluded.append({'gameId':game['id'],'playerId':definition['playerId'],'stat':definition['stat'],'reason':'Exact final statistic and positive participation evidence were unavailable; no zero/outcome was invented.'})
                continue
            estimate = probabilities[definition['id']]
            p = estimate['probability']
            y = int(actual > definition['threshold'])
            clipped = min(1-1e-12,max(1e-12,p))
            observations.append({'gameId':game['id'],'playerId':definition['playerId'],'team':definition['team'],'stat':definition['stat'],'threshold':definition['threshold'],'operator':'gt','actual':actual,'outcome':y,'rawProbability':p,'calibratedProbability':None,'brier':(p-y)**2,'logLoss':-y*math.log(clipped)-(1-y)*math.log(1-clipped),'monteCarloInterval95':estimate['monteCarloInterval95'],'simulations':simulations,'trainingOpportunities':definition['trainingOpportunities'],'retrospective':True})
        game_results.append({**game,'eventStartMeaning':'Earliest actual source time_of_day, not an invented scheduled kickoff','simulations':simulations,'scoreHistogramCounts':{team:sum(row['count'] for row in distribution['histogram']) for team,distribution in result['scoreDistributions'].items()},'modelVersion':result['modelVersion']})
    if not observations:
        raise ValueError('No exact heldout final player statistics matched the fixed training-selected identities.')
    diagnostic = []
    for index in range(10):
        group = [row for row in observations if min(9,int(row['rawProbability']*10)) == index]
        diagnostic.append({'from':index/10,'to':(index+1)/10,'n':len(group),'predicted':sum(row['rawProbability'] for row in group)/len(group) if group else None,'observed':sum(row['outcome'] for row in group)/len(group) if group else None,'interval95':None})
    return {'protocol':PROTOCOL,'status':'retrospective_research_only','createdAt':datetime.now(timezone.utc).isoformat(),'season':season,'trainingThroughWeek':train_week,'heldoutWeek':heldout_week,'fixedThresholds':{stat:threshold for stat,_,threshold in THRESHOLDS},'selection':'First heldout games by actual recorded event time; each team\'s prior-prefix volume leader per statistic; no heldout statistic is used to select a player or threshold.','cutoff':cutoff,'trainingPlays':len(model['rows']),'trainingGames':len({row['game'] for row in model['rows']}),'n':len(observations),'games':game_results,'observations':observations,'excluded':excluded,'brier':sum(row['brier'] for row in observations)/len(observations),'logLoss':sum(row['logLoss'] for row in observations)/len(observations),'calibrationDiagnostic':diagnostic,'calibrationStatus':'INSUFFICIENT EVIDENCE. Small retrospective cohort; no approved player-prop calibrator.','calibratedProbabilitiesAvailable':False,'productionEligible':False,'promotion':'NOT PROMOTED','marketBenchmark':None,'inputConversion':conversion,'sources':[pbp.metadata,stats.metadata],'historicalFirstPublicationVerified':False,'prospectiveSnapshotsCreated':0,'personalFinancialRecordsChanged':False,'limitations':['Current public files were collected after these historical games. Historical first-publication times and later revisions cannot be verified; this is not a prospective accuracy claim.','Small fixed holdout and correlated player contracts do not establish calibration or market advantage. Sampling intervals describe simulation noise only.','Historical participation/usage is reused; injuries, active/limited/inactive mixtures, numerical weather effects and future roster changes are not fitted in this audit.','The selected thresholds are predeclared research thresholds, not invented historical DraftKings quotes. Unavailable market prices/fees remain unavailable.']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--season',type=int,default=2026)
    parser.add_argument('--train-week',type=int,default=6)
    parser.add_argument('--heldout-week',type=int,default=7)
    parser.add_argument('--games',type=int,default=2)
    parser.add_argument('--simulations',type=int,default=10000)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    report=audit(args.season,args.train_week,args.heldout_week,args.games,args.simulations)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({key:report[key] for key in ('status','n','brier','logLoss','calibrationStatus','promotion')}))


if __name__=='__main__':
    main()
