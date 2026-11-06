"""Availability preflight for future experimental forecasts.
Projected depth-chart rank is not confirmed eligibility. Conflicting starting
QB evidence yields unweighted scenarios; no invented injury probabilities.
This does not retroactively change any archived forecast or result.
"""
from .football import participant_roles

def availability_plan(model,team,event_start,lineup=None,computed_roles=None):
    supplied=dict(lineup or {});roles=computed_roles if computed_roles is not None else participant_roles(model,team,supplied,event_start);latest=max(model['histories'][team].values(),key=lambda h:h['at']);eligible={p:n for p,n in latest['qb'].items() if p not in roles['inactive']}
    recent=max(eligible,key=eligible.get) if eligible else None;chosen=roles['quarterback'];confirmed=roles.get('verified') is True;conflict=bool(recent and recent!=chosen and not confirmed)
    unknown=not roles['injuriesComplete'];ids=sorted({chosen,recent} if conflict else {chosen})
    return {'team':team,'sport':model['sport'],'status':'unweighted_qb_scenarios' if conflict else 'conditional_availability_unknown' if unknown else 'verified_personnel_assumption','selectedQuarterback':chosen,'recentObservedQuarterback':recent,'projectedIsConfirmed':confirmed,'injuriesComplete':roles['injuriesComplete'],'missingAvailabilityMeansHealthy':False,'publishUnconditionalProbability':not(conflict or unknown),'scenarios':[{'quarterback':pid,'weight':None,'interpretation':'Conditional on this quarterback being available; no learned availability weight exists.'} for pid in ids],'reason':'Projected depth-chart quarterback differs from the latest observed quarterback. An unverified rank cannot settle an injury/return question.' if conflict else 'Complete verified pregame availability is missing.' if unknown else 'Explicit source assumptions passed; model validation gates still apply.'}
