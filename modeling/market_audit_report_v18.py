"""Paired regression reporting, separate from frozen simulation execution.

The exposed V15 cohort is not an untouched forecasting test. All deltas are
reported, including regressions. A report is never used to select parameters.
"""
from collections import defaultdict
import numpy as np

VERSION = 'market-regression-report-18.0.0'


def paired_mean_interval(deltas, seed=180018, replicates=2000):
    values = np.asarray(deltas, dtype=float)
    if not len(values):
        return None
    if not np.isfinite(values).all():
        raise ValueError('Nonfinite paired regression observation')
    rng = np.random.default_rng(seed)
    means = values[rng.integers(0, len(values), (replicates, len(values)))].mean(axis=1)
    return {'difference': float(values.mean()),
            'interval95': np.quantile(means, [.025, .975]).tolist(),
            'resamplingUnit': 'game', 'replicates': replicates, 'seed': seed}


def game_metrics(rows):
    if not rows:
        return None
    metrics = {}
    for name, current, previous in [
        ('teamScoreMAE', [np.mean(np.abs(r['scoreErrors'])) for r in rows],
         [np.mean(np.abs(r['baselineScoreErrors'])) for r in rows]),
        ('Brier', [r['brier'] for r in rows], [r['baselineBrier'] for r in rows]),
        ('logLoss', [r['logLoss'] for r in rows], [r['baselineLogLoss'] for r in rows]),
    ]:
        metrics[name] = {'original': float(np.mean(previous)),
                         'repaired': float(np.mean(current)),
                         'pairedGameDelta': paired_mean_interval(np.array(current)-previous)}
    return {'games': len(rows), **metrics}


def player_metrics(rows):
    by_stat = defaultdict(list)
    for row in rows:
        for player in row['players']:
            by_stat[player['stat']].append((row['gameId'], player))
    result = {}
    for stat, observations in sorted(by_stat.items()):
        grouped = defaultdict(list)
        for game_id, player in observations:
            grouped[game_id].append(player)
        rng = np.random.default_rng(180018)
        games = list(grouped.values())
        # Resample whole games, preserving all within-game player correlations.
        totals = np.array([[sum(abs(p['error'])-abs(p['oldError']) for p in ps), len(ps)] for ps in games])
        draws = totals[rng.integers(0, len(totals), (2000, len(totals)))].sum(axis=1)
        differences = draws[:, 0]/draws[:, 1]
        current = np.array([p['error'] for _, p in observations])
        previous = np.array([p['oldError'] for _, p in observations])
        result[stat] = {'games': len(games), 'matchedPlayerObservations': len(observations),
                        'originalMAE': float(np.mean(abs(previous))),
                        'repairedMAE': float(np.mean(abs(current))),
                        'repairedRMSE': float(np.sqrt(np.mean(current**2))),
                        'originalBias': float(previous.mean()), 'repairedBias': float(current.mean()),
                        'repairedInterval90Coverage': float(np.mean([p['covered90'] for _, p in observations])),
                        'pairedGameBlockMAEDelta95': np.quantile(differences, [.025, .975]).tolist(),
                        'intervalsAreMonteCarloPredictiveNotModelConfidence': True}
    return result


def audit_report(rows, expected_ids):
    ids = [r['gameId'] for r in rows]
    if len(set(ids)) != len(ids) or set(ids) != set(expected_ids):
        raise ValueError('Regression report requires the exact frozen cohort, without duplicates')
    if any(r['simulations'] != 10000 or not r['accountingReconciled'] for r in rows):
        raise ValueError('Complete-game simulation or accounting audit failed')
    result = {'version': VERSION, 'scope': 'exposed_regression_not_independent_accuracy',
              'primaryMetric': 'CLV', 'CLV': None, 'verifiedClosingQuoteGames': 0,
              'games': len(rows), 'simulatedCompleteGames': sum(r['simulations'] for r in rows),
              'strictPregameQualifiedGames': sum(bool(r['strictPregameQualified']) for r in rows),
              'tunedOnAudit': False, 'productionPromotion': False, 'leagues': {}}
    for sport in sorted({r['sport'] for r in rows}):
        league = [r for r in rows if r['sport'] == sport]
        result['leagues'][sport] = {
            'gameMetrics': game_metrics(league), 'playerMetrics': player_metrics(league),
            'byOriginalModelVersion': {v: game_metrics([r for r in league if r['baselineVersion'] == v])
                                       for v in sorted({r['baselineVersion'] for r in league})}}
    return result
