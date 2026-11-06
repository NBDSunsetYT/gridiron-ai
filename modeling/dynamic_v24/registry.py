"""Independent head selection. Marginal winners cannot replace a joint model."""
from ..overnight_v20.state import atomic,digest,read
FOOTBALL=('passingAttempts','passingYards','passingTouchdowns','interceptions','carries','rushingYards','rushingTouchdowns','targets','receptions','receivingYards','receivingTouchdowns','teamPoints','moneyline','spread','total')
NBA=('minutes','points','rebounds','assists','threePointersMade','steals','blocks','turnovers','pointsReboundsAssists','pointsRebounds','pointsAssists','reboundsAssists','doubleDouble','tripleDouble','teamPoints','moneyline','spread','total')
FAMILIES=('rolling5','ewma','opponent_ridge','lasso','elastic_net','hierarchical','boosted','quantile','negative_binomial','hurdle','mixture','empirical_bayes','ensemble','joint_monte_carlo')
def catalogue():return {s:{k:{'status':'unreviewed','productionPromotion':False,'jointReplacementAllowed':False} for k in (NBA if s=='NBA' else FOOTBALL)} for s in ('NFL','CFB','NBA')}
def decision(windows,*,alpha=.05/48,min_games=30):
    if len(windows)<2 or any(w.get('games',0)<min_games for w in windows):return {'accepted':False,'reason':'insufficient_independent_windows_or_games'}
    if any(w.get('criticalQualityFailure') for w in windows):return {'accepted':False,'reason':'critical_evidence_failure'}
    if any(w.get('deltaCIAdjusted',[0,1])[1]>=0 for w in windows):return {'accepted':False,'reason':'improvement_not_credible_across_windows'}
    if any(w.get('intervalCoverageRegression',0)>.03 for w in windows):return {'accepted':False,'reason':'prediction_interval_regression'}
    return {'accepted':True,'reason':'conditional_research_candidate_only','productionPromotion':False,'jointReplacementAllowed':False}
class Registry:
    def __init__(self,path):self.path=path
    def register(self,record):
        if record.get('productionPromotion') is not False:raise ValueError('No automatic production promotion')
        state=read(self.path,{'versions':[],'researchChampions':{}});record={**record,'id':digest(record)}
        if any(r['id']==record['id'] for r in state['versions']):return record['id']
        state['versions'].append(record)
        if record.get('accepted'):state['researchChampions'][record['sport']+':'+record['stat']]=record['id']
        atomic(self.path,state);return record['id']
