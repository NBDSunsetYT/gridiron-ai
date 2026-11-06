"""Objective modes are orthogonal to V23's mechanics/evidence modes.

All scoring consumes an already frozen prediction. No fitting, simulation,
market imputation or production promotion happens in this module.
"""
from enum import Enum
import math
import numpy as np
from ..overnight_v20.state import digest

VERSION = 'accuracy-objectives-25.2'


class AccuracyMode(str, Enum):
    PROBABILITY = 'A_probability'
    NUMERICAL = 'B_numerical'
    MARKET = 'C_market_research'


def objective(output):
    mapping = {'probability': AccuracyMode.PROBABILITY, 'mean': AccuracyMode.NUMERICAL,
               'median': AccuracyMode.NUMERICAL, 'quantile': AccuracyMode.NUMERICAL,
               'market_edge': AccuracyMode.MARKET}
    if output not in mapping:
        raise ValueError('Explicit numerical, probability or market objective required')
    return mapping[output]


def score_numerical(observed, point, draws):
    y, p, x = np.asarray(observed, float), np.asarray(point, float), np.asarray(draws, float)
    if y.ndim != 1 or p.shape != y.shape or x.ndim != 2 or x.shape[0] != len(y) or x.shape[1] < 2 or not len(y):
        raise ValueError('Aligned nonempty observations, points and predictive draws required')
    if not all(np.isfinite(v).all() for v in (y, p, x)):
        raise ValueError('Nonfinite forecast or outcome')
    error = p-y
    intervals = {}
    for level in (.5, .8, .9, .95):
        alpha = 1-level
        lo, hi = np.quantile(x, [alpha/2, 1-alpha/2], axis=1)
        winkler = hi-lo + 2/alpha*np.maximum(lo-y, 0) + 2/alpha*np.maximum(y-hi, 0)
        intervals[str(level)] = {'coverage': float(np.mean((lo <= y) & (y <= hi))),
                                 'meanWidth': float(np.mean(hi-lo)), 'winkler': float(np.mean(winkler))}
    quantiles = {}
    for q in (.05, .1, .25, .5, .75, .9, .95):
        residual = y-np.quantile(x, q, axis=1)
        quantiles[str(q)] = float(np.mean(np.maximum(q*residual, (q-1)*residual)))
    ordered = np.sort(x, axis=1); n = x.shape[1]
    crps = np.mean(np.abs(x-y[:, None]), axis=1)-np.sum((2*np.arange(1,n+1)-n-1)*ordered,axis=1)/n**2
    return {'observations': len(y), 'mae': float(np.mean(np.abs(error))),
            'rmse': float(np.sqrt(np.mean(error**2))), 'bias': float(np.mean(error)),
            'medianAbsoluteError': float(np.median(np.abs(error))), 'crps': float(np.mean(crps)),
            'quantileLoss': quantiles, 'intervals': intervals}


def score_probability(observed, probability):
    y, p = np.asarray(observed, float), np.asarray(probability, float)
    if y.ndim != 1 or p.shape != y.shape or not len(y) or not np.isfinite(p).all() or not np.isin(y, [0, 1]).all() or np.any((p<0)|(p>1)):
        raise ValueError('Aligned binary outcomes and probabilities in [0,1] required')
    # Clipping is solely a documented numerical evaluation convention, not calibration.
    clipped = np.clip(p, 1e-12, 1-1e-12)
    buckets = np.minimum(9, (p*10).astype(int)); reliability = []
    for bucket in range(10):
        mask = buckets == bucket
        if np.any(mask):
            reliability.append({'bucket': bucket, 'count': int(mask.sum()),
                                'predicted': float(p[mask].mean()), 'observed': float(y[mask].mean())})
    return {'observations': len(y), 'brier': float(np.mean((p-y)**2)),
            'logLoss': float(np.mean(-y*np.log(clipped)-(1-y)*np.log1p(-clipped))),
            'logLossClipEpsilon': 1e-12, 'reliability': reliability,
            'ece': sum(r['count']/len(y)*abs(r['predicted']-r['observed']) for r in reliability)}


def threshold_probability(draws, threshold, side, *, equality='push'):
    """Exact threshold semantics; pushes are never silently counted as losses.

    rawProbability is the unconditional win frequency. Conditional non-push
    probability is separate. Model uncertainty is not Monte Carlo uncertainty.
    """
    x = np.asarray(draws, float)
    if x.ndim != 1 or not len(x) or not np.isfinite(x).all() or isinstance(threshold, bool) or not math.isfinite(threshold):
        raise ValueError('Actual finite scalar distribution and exact threshold required')
    if side not in ('over', 'under') or equality not in ('push', 'win', 'lose'):
        raise ValueError('Explicit outcome and equality settlement required')
    equal = x == threshold
    hit = x > threshold if side == 'over' else x < threshold
    if equality == 'win': hit = hit | equal
    k, n = int(hit.sum()), len(x); p = k/n
    pushes = int(equal.sum()) if equality == 'push' else 0
    from ..simulator import wilson
    return {'successfulOutcomes': k, 'validGames': n, 'rawProbability': p,
            'pushOutcomes': pushes, 'nonPushProbability': k/(n-pushes) if n>pushes else None,
            'monteCarloSE': math.sqrt(p*(1-p)/n), 'monteCarloInterval95': wilson(k,n),
            'calibratedProbability': None, 'modelUncertainty': 'not_fully_quantified'}


def stamp_mode(mode, snapshot_hash, model_version, prediction):
    payload = {'version': VERSION, 'accuracyMode': AccuracyMode(mode).value,
               'snapshotHash': snapshot_hash, 'modelVersion': model_version,
               'prediction': prediction, 'productionPromotion': False}
    return payload | {'predictionHash': digest(payload)}
