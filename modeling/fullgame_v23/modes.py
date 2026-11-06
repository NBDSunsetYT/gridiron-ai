"""Three non-interchangeable research modes; finals never qualify a forecast."""
from enum import Enum
from ..integration_v22.datasets import protected
class Mode(str,Enum):
    MECHANICS='historical_mechanics'
    CONDITIONAL='conditional_diagnostic'
    FORECAST='strict_pregame_forecast'
def context(mode,sport,event,sources,cutoff=None):
    mode=Mode(mode)
    if sport not in ('NFL','CFB','NBA') or event in protected():raise ValueError('Unsupported sport or protected event')
    if not sources or any(not s.get('sourceVersion') or not str(s.get('source','')).startswith('https://') for s in sources):raise ValueError('Versioned public evidence required')
    if mode==Mode.FORECAST and not cutoff:raise ValueError('Pregame cutoff required')
    return {'mode':mode.value,'sport':sport,'eventId':event,'sources':sources,'cutoff':cutoff,'finalInformationAllowed':mode==Mode.MECHANICS,'accuracyClaimAllowed':mode==Mode.FORECAST,'bettingAccuracyClaimAllowed':False,'productionPromotionAllowed':False}
def label(result,ctx):
    result={**result,'researchContext':ctx,'productionEligible':False}
    if ctx['mode']!=Mode.FORECAST:
        for key in ['calibratedProbability','homeWinProbability','awayWinProbability','brierScore','logLoss','bettingROI','accuracy']:result.pop(key,None)
        result['notAPregamePrediction']=True
    return result
