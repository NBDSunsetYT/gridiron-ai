"""Frozen chronological evaluation using the existing V24 statistical law.

This module does not fit models, choose families, open sealed outcomes, or
convert conditional corrected-history diagnostics into strict forecasts.
"""
from datetime import timedelta
import numpy as np
from ..accuracy_v20.quality import aware
from ..dynamic_v24.completion.data import LABELS
from ..dynamic_v24.completion.selection import evaluate, paired_loss
from ..overnight_v20.state import digest

VERSION='frozen-accuracy-evaluation-25.1'


def feature_guard(rows, training_through, *, evidence_tier):
    if evidence_tier not in ('conditional_corrected_history','strict_pregame') or not rows:
        raise ValueError('Explicit evidence tier and nonempty forecast features required')
    seen=set()
    for row in rows:
        if LABELS.intersection(row):raise ValueError('Outcome labels cannot enter prediction features')
        key=tuple(row.get(k) for k in ('gameId','team','player','stat'))
        if None in key or key in seen:raise ValueError('Missing or duplicate event/team/player/stat identity')
        seen.add(key);event=aware(row.get('at'))
        if aware(training_through)>=event:raise ValueError('Fit/selection must strictly precede every forecast event')
        if aware(row.get('featureLastGame'))>=event-timedelta(hours=48):raise ValueError('Earlier-game embargo violated')
        if evidence_tier=='strict_pregame':
            if not row.get('sourceEditionVerified') or row.get('missingEvidence') or row.get('missingAvailability'):
                raise ValueError('Missing point-in-time publication/availability evidence')
            for field in ('statisticsPublishedAt','injuryPublishedAt','lineupPublishedAt','participationPublishedAt'):
                if aware(row.get(field))>=event:raise ValueError('Pregame evidence must be published before prediction cutoff')
    return {'rows':len(rows),'games':len({r['gameId'] for r in rows}),
            'featureDigest':digest(rows),'evidenceTier':evidence_tier,'productionEligible':False}


def cohort_guard(cohorts, protected_ids):
    """Metadata-only check; never read final-test labels or sources."""
    if set(cohorts)!={'development','validation','confirmation','final'}:
        raise ValueError('Four distinct chronological cohort roles required')
    previous=None;seen=set()
    for name in ('development','validation','confirmation','final'):
        rows=cohorts[name]
        if not rows:raise ValueError('Empty cohort: '+name)
        ids={r['gameId'] for r in rows};times=[aware(r['eventAt']) for r in rows]
        if len(ids)!=len(rows) or seen&ids:raise ValueError('Game crosses chronological cohort boundary')
        if previous is not None and min(times)<=previous:raise ValueError('Cohort periods overlap or include simultaneous future games')
        if name!='final' and ids&set(protected_ids):raise ValueError('Protected game in development/validation/confirmation')
        if name=='final' and any(r.get('alreadyExposed') is not False for r in rows):raise ValueError('Unknown or exposed final period is not verified untouched')
        previous=max(times);seen|=ids
    return digest(cohorts)


def score_frozen(rows, point, draws, thresholds):
    if len(rows)!=len(point) or len(rows)!=len(draws) or not len(rows):raise ValueError('Prediction/label cardinality differs')
    point=np.asarray(point,float);draws=np.asarray(draws,float)
    if point.ndim!=1 or draws.ndim!=2 or draws.shape[1]<2 or not np.isfinite(point).all() or not np.isfinite(draws).all():
        raise ValueError('Finite point estimates and actual predictive draws required')
    if any(r.get('y') is None or not np.isfinite(r['y']) for r in rows):raise ValueError('Verified observed labels required for grading')
    result=evaluate(rows,point,draws,thresholds)
    result.update(evaluationVersion=VERSION,jointProbabilityCalibration=None,
                  jointProbabilityReason='Marginal traces cannot establish joint-game calibration',
                  marketLineCalibration=None,marketless=True)
    return result


def paired_game_comparison(rows, reference, challenger, purpose):
    if purpose not in ('expected_value','median'):raise ValueError('Use an explicit proper-score comparison for distribution heads')
    return paired_loss(rows,reference,challenger,loss='squared' if purpose=='expected_value' else 'absolute')
