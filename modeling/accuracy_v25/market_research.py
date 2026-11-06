"""Verified-market math for research, never a synthetic replacement feed.

Sportsbook two-sided decimal odds support multiplicative and Shin devigging.
Event contracts retain their separate payout/fee semantics and are not silently
normalized into sportsbook probabilities. Closing observations are grading-only.
"""
import math
from scipy.optimize import brentq, minimize_scalar
from scipy.special import expit, logit
import numpy as np
from ..accuracy_v20.quality import aware
from ..overnight_v20.state import digest


def devig(decimal_odds):
    odds=np.asarray(decimal_odds,float)
    if odds.ndim!=1 or len(odds)<2 or not np.isfinite(odds).all() or np.any(odds<=1):
        raise ValueError('Verified decimal odds > 1 for every mutually exclusive outcome required')
    q=1/odds;total=float(q.sum())
    if total<1-1e-10:raise ValueError('Shin bookmaker model does not support an underround')
    normalized=q/total
    if abs(total-1)<1e-10:return {'multiplicative':normalized.tolist(),'shin':normalized.tolist(),'shinZ':0.}
    def probabilities(z):return (np.sqrt(z*z+4*(1-z)*q*q/total)-z)/(2*(1-z))
    z=brentq(lambda z:float(probabilities(z).sum()-1),0,1-1e-8)
    shin=probabilities(z)
    if np.any(shin<0) or abs(shin.sum()-1)>1e-7:raise ValueError('Invalid Shin solution')
    return {'multiplicative':normalized.tolist(),'shin':shin.tolist(),'shinZ':float(z)}


def quote_guard(quote, identity, *, cutoff, grading=False):
    if quote is None:return None
    if quote.get('verified') is not True or not quote.get('sourceVersion') or not str(quote.get('source','')).startswith('https://'):
        raise ValueError('Verified source edition required')
    if quote.get('identity')!=identity or quote.get('identityHash')!=digest(identity):
        raise ValueError('Market player/event/stat/threshold/product/settlement mismatch')
    if not identity.get('settlementVersion') or identity.get('product') not in ('sportsbook','event_contract'):
        raise ValueError('Explicit market product and settlement edition required')
    published=aware(quote['publishedAt']);captured=aware(quote['capturedAt']);available=aware(quote['availableAt'])
    if published>available or captured>available or available>=aware(cutoff):
        raise ValueError('Market observation was not available before the allowed cutoff')
    if quote.get('designation')=='closing' and not grading:
        raise ValueError('Closing observations are grading-only, never pregame model features')
    if identity['product']=='event_contract':
        raise ValueError('Event-contract fee/payout adapter required; sportsbook devigging is incompatible')
    if not quote.get('book') or quote.get('suspended') is not False:
        raise ValueError('Verified available book/outcomes required')
    return devig(quote['decimalOdds'])


def compare_market(model_probability, quote, identity, *, cutoff, closing=None, event_at=None):
    if not math.isfinite(model_probability) or not 0<=model_probability<=1:
        raise ValueError('Actual independent model probability required')
    base={'modelProbability':float(model_probability),'marketProbability':None,'modelMarketDifference':None,
          'clvProbabilityPoints':None,'returnDistribution':None,'marketBlendedProbability':None,
          'fitWeight':None,'modeCEligible':False,'researchOnly':True}
    if quote is None:return base|{'status':'market_data_unavailable','marketObservations':0}
    probabilities=quote_guard(quote,identity,cutoff=cutoff)
    index=identity.get('outcomeIndex')
    if isinstance(index,bool) or not isinstance(index,int) or not 0<=index<len(probabilities['shin']):
        raise ValueError('Exact mutually exclusive market outcome index required')
    p=probabilities['shin'][index]
    result=base|{'status':'verified_market_comparison_only','marketObservations':1,
                 'marketProbability':p,'multiplicativeProbability':probabilities['multiplicative'][index],
                 'modelMarketDifference':float(model_probability-p),'quoteTimestamp':quote['capturedAt'],
                 'provider':quote['source'],'devigMethod':'shin_candidate_not_validated_prior'}
    if closing is not None:
        if not event_at or closing.get('designation')!='closing' or quote.get('designation')!='opening' or aware(closing['capturedAt'])<=aware(quote['capturedAt']):
            raise ValueError('Authentic ordered opening and closing observations required')
        closed=quote_guard(closing,identity,cutoff=event_at,grading=True)
        if closing.get('book')!=quote.get('book'):raise ValueError('CLV must use the same book and settlement definition')
        result['clvProbabilityPoints']=closed['shin'][index]-p
    return result


def fit_logit_blend(rows, *, fit_cutoff):
    """One bounded development-only candidate. This does not approve a route.

    Prediction records already bind exact verified markets. Callers must evaluate
    this fit on separate later validation; no fixed weight is imposed.
    """
    if len({r['gameId'] for r in rows})<30:raise ValueError('Thirty development game blocks required')
    if any(r.get('role')!='development' or r.get('evidenceTier')!='strict_pregame' or r.get('marketVerified') is not True or r.get('settlementVerified') is not True for r in rows):
        raise ValueError('Only independently verified development observations may fit a blend')
    for r in rows:
        if not aware(r['trainingThrough'])<aware(r['forecastAt'])<aware(r['eventAt'])<aware(r['settledAt'])<aware(fit_cutoff):
            raise ValueError('Blend development timeline leaks future information')
        if aware(r['marketAvailableAt'])>=aware(r['forecastAt']):raise ValueError('Future market information')
    p=np.asarray([r['modelProbability'] for r in rows],float);q=np.asarray([r['deviggedMarketProbability'] for r in rows],float);y=np.asarray([r['outcome'] for r in rows],float)
    if not np.isfinite(p).all() or not np.isfinite(q).all() or np.any((p<=0)|(p>=1)|(q<=0)|(q>=1)) or not np.isin(y,[0,1]).all():
        raise ValueError('Finite interior model/devigged probabilities and binary settlements required')
    # Equal game weights prevent games with many props dominating the objective.
    counts={g:sum(r['gameId']==g for r in rows) for g in {r['gameId'] for r in rows}}
    weight=np.asarray([1/counts[r['gameId']] for r in rows]);a,b=logit(p),logit(q)
    loss=lambda w:float(np.average((expit(w*a+(1-w)*b)-y)**2,weights=weight))
    fit=minimize_scalar(loss,bounds=(0,1),method='bounded')
    if not fit.success:raise ValueError('Blend optimizer did not converge')
    w=min([0.,1.,float(fit.x)],key=loss)
    return {'modelWeight':w,'marketWeight':1-w,'developmentBrier':loss(w),'fitThrough':fit_cutoff,
            'developmentGames':len(counts),'inputHash':digest(rows),'productionEligible':False,
            'independentValidationRequired':True,'probabilityCalibrator':None}
