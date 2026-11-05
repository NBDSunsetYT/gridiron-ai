"""Predefined accuracy/reliability guardrails. Research does not auto-promote."""
def review(league,sport,family):
    primary='rebounds' if sport=='NBA' else 'passingYards';candidate=league['phaseBenchmarks']['validation'].get(primary,{}).get(family);reasons=[]
    if not candidate:return {'status':'not_evaluated','reasons':['No later-window paired validation results'],'productionPromotion':False}
    if candidate['games']<200:reasons.append('Fewer than 200 independent matched validation games')
    delta=candidate.get('primaryMAEDelta',candidate['pairedMAEDelta'])
    if not delta or delta['bootstrap95'][1]>=0:reasons.append('Game-clustered 95% interval does not establish lower MAE')
    if candidate['metrics']['mae']>.99*candidate['baseline']['mae']:reasons.append('Primary MAE improvement is less than predefined 1%')
    if len([w for w in league['walkForward'] if w['phase']=='validation'])<3:reasons.append('Fewer than three chronological validation windows')
    important=['points','assists','minutes'] if sport=='NBA' else ['passingAttempts','receivingYards','rushingYards']
    regressions=[]
    for stat in important:
        c=league['phaseBenchmarks']['validation'].get(stat,{}).get(family)
        if c and c['baseline']['mae']>0 and c['metrics']['mae']>1.03*c['baseline']['mae']:regressions.append(stat)
    if regressions:reasons.append('Important-category MAE regressed more than 3%: '+', '.join(regressions))
    coverage=league['evidenceCoverage']
    if coverage['completePointInTimeGames']<.9*coverage['games']:reasons.append('Original point-in-time availability/lineup coverage below 90%')
    reasons.append('This point-head candidate lacks matched joint-game Brier/log-loss/interval validation')
    return {'status':'rejected_for_promotion','primary':primary,'matchedValidationGames':candidate['games'],'pairedPrimaryDelta':delta,'importantCategoryRegressions':regressions,'reasons':reasons,'productionPromotion':False,'researchOnly':True}
