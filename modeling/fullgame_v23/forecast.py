"""Strict Mode B gate. Mechanics success never supplies pregame evidence."""
from ..accuracy_v20.quality import aware
from ..evidence_v21.tiers import classify
from ..integration_v22.gates import audit as football_audit
from ..integration_v22.datasets import protected
from ..overnight_v20.state import digest
from .modes import Mode

def qualify(model,match,ctx,evidence,certificate):
    if ctx['mode']!=Mode.FORECAST or ctx.get('finalInformationAllowed'):raise ValueError('Mode A/C cannot enter the pregame forecasting pipeline')
    reasons=[]
    if ctx.get('eventId')!=match['id'] or ctx.get('sport')!=model['sport']:reasons.append('context_identity_mismatch')
    if ctx.get('cutoff')!=match['cutoff']:reasons.append('context_cutoff_mismatch')
    if model.get('sha256')!=digest({k:v for k,v in model.items() if k!='sha256'}):reasons.append('model_content_checksum')
    if match['id'] in protected() or set(model.get('trainingGameIds',[]))&protected():reasons.append('protected_cohort')
    if model.get('inputPolicy')!='point_in_time':reasons.append('model_inputs_not_point_in_time')
    try:
        if aware(model.get('asOf',model.get('cutoff')))>=aware(match['cutoff']):reasons.append('model_does_not_precede_cutoff')
    except ValueError:reasons.append('model_cutoff_unverified')
    if model['sport'] in ('NFL','CFB'):
        result=football_audit(model,match,evidence,certificate)
    else:
        checks=('regulation_clock_conservation','five_player_seconds','scoring_accounting','rebound_opportunities','foul_substitution_rules','overtime_accounting')
        bad=[]
        if not certificate or certificate.get('modelHash')!=model.get('sha256'):bad.append('missing_model_bound_certificate')
        else:
            if len(set(certificate.get('independentGames',[])))<12:bad.append('twelve_independent_mechanics_games_not_verified')
            bad.extend(k for k in checks if certificate.get('checks',{}).get(k) is not True)
            if certificate.get('sha256')!=digest({k:v for k,v in certificate.items() if k!='sha256'}):bad.append('certificate_checksum')
        result=classify('NBA',match['id'],match['cutoff'],evidence.get('components',{}),model_uncertainty=evidence.get('modelUncertainty'),consistency={k:False for k in bad} or {'mechanics':True});result['reasons']=bad+result['missingDomains']+result['warnings']
    result['reasons']=reasons+result['reasons'];result['strictQualified']=not result['reasons'] and result['fullGameSimulationAllowed'];result['productionPromotionAllowed']=False;return result
def require(model,match,ctx,evidence,certificate):
    q=qualify(model,match,ctx,evidence,certificate)
    if not q['strictQualified']:raise ValueError('Pregame simulation withheld: '+', '.join(q['reasons']))
    return q

def compact(result):
    """Persist aggregates and <=3 representative games, never 10k play tapes."""
    from collections import Counter,defaultdict
    from ..simulator import histogram_summary,wilson
    import numpy as np,math
    rows=result['results'];n=len(rows);scores={t:Counter(r['scores'][t] for r in rows) for t in rows[0]['scores']};players=defaultdict(lambda:defaultdict(Counter));all_players=set(p for r in rows for p in r['players']);stats={p:set(k for r in rows for k in r['players'].get(p,{})) for p in all_players}
    for r in rows:
        for p in all_players:
            for k in stats[p]:players[p][k][r['players'].get(p,{}).get(k,0)]+=1
    teams=list(scores);wins={t:sum(r['scores'][t]>r['scores'][next(o for o in teams if o!=t)] for r in rows) for t in teams};ties=sum(len(set(r['scores'].values()))==1 for r in rows);summary={t:{'successfulOutcomes':k,'validGames':n,'rawProbability':k/n,'monteCarloSE':math.sqrt(k/n*(1-k/n)/n),'monteCarloInterval95':wilson(k,n),'calibratedProbability':None} for t,k in wins.items()}
    a=np.array([r['scores'][teams[0]] for r in rows],float);b=np.array([r['scores'][teams[1]] for r in rows],float);correlation=float(np.corrcoef(a,b)[0,1]) if a.std()>0 and b.std()>0 else None
    if result['researchContext']['mode']!=Mode.FORECAST:summary=None
    return {k:v for k,v in result.items() if k!='results'}|{'scoreDistributions':{t:histogram_summary(v,n) for t,v in scores.items()},'totalDistribution':histogram_summary(Counter(r['scores'][teams[0]]+r['scores'][teams[1]] for r in rows),n),'marginDistribution':histogram_summary(Counter(r['scores'][teams[0]]-r['scores'][teams[1]] for r in rows),n),'jointScoreCorrelation':correlation,'teamWinFrequencies':summary,'tieOutcomes':ties,'playerDistributions':{p:{k:histogram_summary(h,n) for k,h in ss.items()} for p,ss in players.items()},'representativeGames':rows[:3],'allSimulatedPlaysPermanentlyStored':False,'modelUncertainty':'Not supplied by Monte Carlo sampling uncertainty','settlementNote':'Raw win frequencies do not specify tie/push/void pricing rules.'}
