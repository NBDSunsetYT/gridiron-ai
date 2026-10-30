"""Small fixed-cutoff holdout audit on a local nflverse dataset; no model promotion."""
import argparse
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from .fit import fit_csv
from .nflverse_adapter import normalize, read_pbp, number, SOURCE
from .simulator import simulate


def audit(path, train_week=12, heldout_week=13, limit=4, simulations=10000):
    raw = Path(path).read_bytes()
    rows = read_pbp(path)
    games, first_recorded = {}, {}
    for row in rows:
        if row.get('season_type') == 'REG' and number(row, 'week') == heldout_week:
            games[row['game_id']] = row
            if row.get('time_of_day'):
                stamp = row['time_of_day']
                game_id = row['game_id']
                first_recorded[game_id] = min(first_recorded.get(game_id, stamp), stamp)
    selected = sorted(games.values(), key=lambda g: (g['game_date'], g['game_id']))[:limit]
    if not selected or heldout_week <= train_week:
        raise ValueError('Chronological non-overlapping training and heldout games required')
    cutoff = min(g['game_date'] for g in selected) + 'T00:00:00Z'
    csv, conversion = normalize(rows, train_week)
    model = fit_csv(csv, SOURCE + '; user must verify permitted usage', cutoff)['model']
    results = []
    for game in selected:
        event_start = first_recorded.get(game['game_id'])
        if not event_start:
            raise ValueError('Heldout game lacks an actual recorded event timestamp')
        report = simulate(model, game['home_team'], game['away_team'], simulations, 2024, event_start)
        actual_home, actual_away = number(game, 'home_score'), number(game, 'away_score')
        observed = int(actual_home > actual_away)
        p = max(1e-12, min(1-1e-12, report['homeWinProbability']))
        results.append({'gameId': game['game_id'], 'home': game['home_team'], 'away': game['away_team'],
                        'actualHome': actual_home, 'actualAway': actual_away, 'eventStart': event_start, 'eventStartMeaning': 'Earliest actual source time_of_day for this game; not an invented scheduled kickoff',
                        'predictedHome': report['scoreDistributions'][game['home_team']]['mean'],
                        'predictedAway': report['scoreDistributions'][game['away_team']]['mean'],
                        'homeWinProbability': p, 'observedHomeWin': observed, 'brier': (p-observed)**2,
                        'logLoss': -math.log(p if observed else 1-p), 'simulations': simulations,
                        'backoffCounts': report['evidence']['backoffCounts']})
    n = len(results)
    return {'source': SOURCE, 'datasetSha256': hashlib.sha256(raw).hexdigest(), 'modelVersion': model['version'],
            'cutoff': cutoff, 'trainThroughWeek': train_week, 'heldoutWeek': heldout_week, 'inputConversion': conversion,
            'validation': 'Fixed chronological cutoff, first heldout games selected before scoring; no tuning on holdout.',
            'n': n, 'brier': sum(r['brier'] for r in results)/n, 'logLoss': sum(r['logLoss'] for r in results)/n,
            'scoreMAE': sum(abs(r['predictedHome']-r['actualHome'])+abs(r['predictedAway']-r['actualAway']) for r in results)/(2*n),
            'games': results, 'createdAt': datetime.now(timezone.utc).isoformat(),
            'promotion': 'NOT PROMOTED. Small preliminary mechanical/holdout audit; insufficient evidence of calibration or market advantage.',
            'limitations': ['Only a small fixed holdout slice; no bootstrap model uncertainty, market benchmark or confidence in superiority.',
                            'Historical player identities/usage are reused; no future roster, injury, weather or true home-field fit.',
                            'Team/down fallback and clock filtering can distort scores. Inspect score errors before using probabilities.']}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('input', type=Path)
    p.add_argument('--train-week', type=int, default=12)
    p.add_argument('--heldout-week', type=int, default=13)
    p.add_argument('--games', type=int, default=4)
    p.add_argument('--simulations', type=int, default=10000)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    if not 1 <= a.games <= 32 or not 1000 <= a.simulations <= 100000:
        raise ValueError('games1..32; simulations1000..100000')
    report = audit(a.input, a.train_week, a.heldout_week, a.games, a.simulations)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(report, indent=2))
    print(json.dumps({k: report[k] for k in ('n','brier','logLoss','scoreMAE','promotion')}))


if __name__ == '__main__':
    main()
