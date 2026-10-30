"""Retrospective chronological game-total baseline. Not a validated trading model.

Reads public nflverse games.csv locally; does not fetch or license any dataset.
The fixed threshold and split are CLI arguments, frozen before evaluation.
"""
import argparse
import csv
import hashlib
import json
import math
import random
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path


def interval(successes, n):
    p, z = successes / n, 1.959963984540054
    denominator = 1 + z*z/n
    center = (p + z*z/(2*n))/denominator
    radius = z*math.sqrt((p*(1-p)+z*z/(4*n))/n)/denominator
    return [max(0, center-radius), min(1, center+radius)]


def evaluate(raw, threshold, training_season, holdout_season, source):
    if not source or not math.isfinite(threshold) or training_season >= holdout_season:
        raise ValueError('Source, finite threshold, and strictly later holdout season required')
    reader = csv.DictReader(raw.splitlines())
    required = {'game_id', 'season', 'gameday', 'home_score', 'away_score', 'game_type', 'week'}
    if not required.issubset(reader.fieldnames or []):
        raise ValueError('Missing game-history columns')
    data, seen = [], set()
    for row in reader:
        if row['game_type'] != 'REG' or not row['home_score'] or not row['away_score']:
            continue
        if not training_season <= int(row['season']) <= holdout_season:
            continue
        if row['game_id'] in seen:
            raise ValueError('Duplicate game identifier')
        seen.add(row['game_id'])
        total = float(row['home_score']) + float(row['away_score'])
        if not math.isfinite(total) or total < 0:
            raise ValueError('Invalid observed score')
        data.append({'game': row['game_id'], 'date': row['gameday'], 'season': int(row['season']),
                     'week': int(row['week']), 'total': total})
    data.sort(key=lambda g: (g['date'], g['game']))
    if len([g for g in data if g['season'] == training_season]) < 100:
        raise ValueError('At least 100 earlier training games required')
    dates = sorted(set(g['date'] for g in data if g['season'] == holdout_season))
    forecasts = []
    # Outcomes on the same date cannot leak between games: fit strictly prior dates.
    for date in dates:
        prior = [g for g in data if g['date'] < date and g['total'] != threshold]
        p = (sum(g['total'] > threshold for g in prior) + .5) / (len(prior)+1)
        for game in data:
            if game['date'] != date or game['season'] != holdout_season or game['total'] == threshold:
                continue
            y = int(game['total'] > threshold)
            forecasts.append({**game, 'p': p, 'y': y, 'trainingGames': len(prior),
                              'brier': (p-y)**2, 'logLoss': -y*math.log(p)-(1-y)*math.log(1-p)})
    if len(forecasts) < 100:
        raise ValueError('At least 100 chronological holdout games required')
    n = len(forecasts)
    brier = sum(f['brier'] for f in forecasts)/n
    calibration = []
    for bucket in range(10):
        group = [f for f in forecasts if min(9, int(f['p']*10)) == bucket]
        if group:
            calibration.append({'from': bucket/10, 'to': (bucket+1)/10, 'n': len(group),
                                'predicted': sum(f['p'] for f in group)/len(group),
                                'observed': sum(f['y'] for f in group)/len(group),
                                'observedWilson95': interval(sum(f['y'] for f in group), len(group))})
    # Resample whole NFL weeks to preserve some within-week dependence.
    weeks = defaultdict(list)
    for f in forecasts:
        weeks[f['week']].append(f)
    rng = random.Random(20261030)
    bootstrap = []
    keys = sorted(weeks)
    for _ in range(1000):
        sample = [f for _ in keys for f in weeks[rng.choice(keys)]]
        bootstrap.append(sum(f['brier'] for f in sample)/len(sample))
    bootstrap.sort()
    return {'modelVersion': 'league-total-empirical-rolling-2.0', 'kind': 'retrospective_baseline_backtest',
            'source': source, 'datasetSha256': hashlib.sha256(raw.encode()).hexdigest(),
            'evaluatedAt': datetime.now(timezone.utc).isoformat(), 'threshold': threshold,
            'trainingSeason': training_season, 'holdoutSeason': holdout_season,
            'n': n, 'trainingGamesAtStart': forecasts[0]['trainingGames'],
            'brier': brier, 'brierWeekBootstrap95': [bootstrap[24], bootstrap[974]],
            'logLoss': sum(f['logLoss'] for f in forecasts)/n,
            'accuracyAtHalf': sum((f['p'] >= .5) == bool(f['y']) for f in forecasts)/n,
            'constantHalfBrier': .25, 'marketBenchmark': None,
            'calibration': calibration, 'observedHitRate': sum(f['y'] for f in forecasts)/n,
            'validation': 'Expanding chronological window; every game predicted once; same-date outcomes excluded from training.',
            'coverage': {'firstHoldoutDate': forecasts[0]['date'], 'lastHoldoutDate': forecasts[-1]['date'], 'weeks': len(weeks)},
            'limitations': ['Fixed league-wide total threshold; no team, player, injury, weather or matchup conditioning.',
                'Historical outcomes retrieved retrospectively; not archived prospective forecasts.',
                'Not a backtest of the play-by-play engine or DraftKings Predictions contracts.',
                'No authorized timestamped exchange prices: fee-aware strategy returns, CLV and market superiority are unavailable.',
                'Calibration only covers the narrow probability range actually emitted; it cannot validate other confidence buckets.',
                'A week-block bootstrap interval does not cover all model or dataset uncertainty.']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('csv')
    parser.add_argument('--source', required=True)
    parser.add_argument('--threshold', required=True, type=float)
    parser.add_argument('--train-season', required=True, type=int)
    parser.add_argument('--holdout-season', required=True, type=int)
    parser.add_argument('--out', required=True)
    args = parser.parse_args()
    report = evaluate(Path(args.csv).read_text(), args.threshold, args.train_season, args.holdout_season, args.source)
    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({key: report[key] for key in ['n', 'brier', 'logLoss', 'brierWeekBootstrap95']}))


if __name__ == '__main__':
    main()
