"""Exact descriptive factor attribution, not a causal diagnosis.

Shapley contributions allocate interactions symmetrically and reconcile to the
signed mean error and absolute error. Missing snap/pace/lineup evidence stays
unidentified. Distributional adequacy must be evaluated separately using CRPS,
coverage and probability scoring; it cannot be inferred from one mean error.
"""
from itertools import permutations
import math

def product(v):return math.prod(v.values())
def factor_attribution(predicted,actual,observed,forecast,unidentified=()):
    if set(predicted)!=set(actual) or not predicted:raise ValueError('Matching named factors required')
    if not all(math.isfinite(v) for v in [*predicted.values(),*actual.values(),observed,forecast]):raise ValueError('Finite factor evidence required')
    keys=list(predicted);signed=dict.fromkeys(keys,0.);absolute=dict.fromkeys(keys,0.);orders=list(permutations(keys))
    if abs(product(actual)-observed)>1e-7*max(1,abs(observed)) or abs(product(predicted)-forecast)>1e-7*max(1,abs(forecast)):raise ValueError('Factorization does not reconstruct forecast/outcome')
    for order in orders:
        x=actual.copy();before=product(x)
        for key in order:
            x[key]=predicted[key];after=product(x);signed[key]+=(after-before)/len(orders);absolute[key]+=(abs(after-observed)-abs(before-observed))/len(orders);before=after
    return {'forecast':forecast,'actual':observed,'signedError':forecast-observed,'absoluteError':abs(forecast-observed),'signedContributions':signed,'absoluteErrorContributions':absolute,'reconciliationResidual':forecast-observed-sum(signed.values()),'absoluteReconciliationResidual':abs(forecast-observed)-sum(absolute.values()),'unidentifiedComponents':list(unidentified),'interpretation':'Algebraic descriptive contributions from matched aggregate outcomes; not causal effects. Contributions may be negative because errors can cancel.','distributionAssumptionContribution':None,'distributionReason':'Not identifiable from a single mean/outcome pair. Inspect interval coverage and proper distribution scores separately.'}
def opportunity_efficiency(predicted_volume,actual_volume,predicted_y,actual_y):
    if min(predicted_volume,actual_volume)<0:raise ValueError('Opportunity counts cannot be negative')
    if predicted_volume==0:return {'available':False,'reason':'Zero predicted opportunities; conditional efficiency cannot be identified','signedError':predicted_y-actual_y}
    pe=predicted_y/predicted_volume
    if actual_volume==0 and actual_y!=0:raise ValueError('Nonzero outcome without supported opportunities')
    ae=actual_y/actual_volume if actual_volume else pe
    result=factor_attribution({'opportunity_volume':predicted_volume,'efficiency':pe},{'opportunity_volume':actual_volume,'efficiency':ae},actual_y,predicted_y,('playing_time_separate_from_opportunities','team_pace_separate_from_opportunities'))
    result.update(available=True,observedEfficiency=None if actual_volume==0 else ae,zeroOpportunityConvention='When actual opportunities are zero, efficiency is unidentifiable and held at the predicted value solely to allocate error to opportunity volume.' if actual_volume==0 else None);return result
def nba_rebound_attribution(predicted_minutes,actual_minutes,predicted_team_duration,actual_team_duration,predicted_opportunities,actual_opportunities,predicted_y,actual_y):
    if min(predicted_minutes,predicted_team_duration,predicted_opportunities)<=0:return {'available':False,'reason':'Predicted on-court rebound exposure is unavailable'}
    pm=predicted_minutes/predicted_team_duration;am=actual_minutes/actual_team_duration if actual_team_duration>0 else None
    if am is None:return {'available':False,'reason':'Actual team duration unavailable'}
    pe=predicted_y/(predicted_opportunities*pm);exposure=actual_opportunities*am
    if exposure==0 and actual_y!=0:return {'available':False,'reason':'Actual rebound exposure inconsistent with counting statistics'}
    ae=actual_y/exposure if exposure else pe
    r=factor_attribution({'rebound_opportunity_volume':predicted_opportunities,'playing_time_fraction':pm,'rebound_share_efficiency':pe},{'rebound_opportunity_volume':actual_opportunities,'playing_time_fraction':am,'rebound_share_efficiency':ae},actual_y,predicted_y,('team_pace_vs_missed_shot_rate','true_on_court_missed_shots','causal_lineup_effect'))
    r.update(available=True,exposureIsMinutesProxy=True,observedReboundShare=None if exposure==0 else ae);return r
