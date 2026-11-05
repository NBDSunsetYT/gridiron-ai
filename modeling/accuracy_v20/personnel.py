"""Bounded conditional QB scenarios, not unverified starting-lineup claims.

The legacy preflight chooses the last starter before consulting replacement
plans. An explicit out can consequently stop a supported backup scenario. This
adapter supplies a prior-supported QB assumption explicitly, preserves all
source flags, and never assigns an injury-availability probability.
"""
import copy,itertools
from ..overnight_v20.models import qb_plans
from ..overnight_v20.football import participant_roles
def conditional_quarterbacks(model,teams,lineups,event_start,maximum_scenarios=4):
    try:plans=qb_plans(model,teams,lineups)
    except ValueError as e:return {'status':'withheld','reason':str(e),'scenarios':[],'unconditionalProbabilityAvailable':False,'simulationsStarted':0}
    supported={};rejected=[]
    for team in teams:
        supported[team]=[]
        for pid in plans[team]['ids']:
            assumption=copy.deepcopy((lineups or {}).get(team,{}));assumption['quarterback']=pid
            # Source verification is never upgraded by a model-generated role.
            if not (lineups or {}).get(team,{}).get('quarterback'):assumption['verified']=False;assumption['projectedSourceVerified']=False
            try:
                if pid not in model['dropback']['participants']:raise ValueError('Quarterback has no fitted earlier dropback evidence')
                roles=participant_roles(model,team,assumption,event_start);supported[team].append({'quarterback':pid,'lineup':assumption,'roles':roles})
            except ValueError as e:rejected.append({'teamId':team,'playerId':pid,'reason':str(e)})
        if not supported[team]:return {'status':'withheld','reason':'No prior-supported conditional quarterback remains for '+team,'scenarios':[],'rejected':rejected,'unconditionalProbabilityAvailable':False}
    count=1
    for team in teams:count*=len(supported[team])
    if count>maximum_scenarios:return {'status':'withheld','reason':'Supported scenario count exceeds declared compute budget','scenarios':[],'candidateScenarios':count,'unconditionalProbabilityAvailable':False}
    scenarios=[]
    for choices in itertools.product(*(supported[t] for t in teams)):
        scenarios.append({'quarterbacks':{t:c['quarterback'] for t,c in zip(teams,choices)},'lineups':{t:c['lineup'] for t,c in zip(teams,choices)},'availabilityWeight':None,'interpretation':'Conditional on the stated previously observed quarterbacks being available; not a confirmed lineup.'})
    return {'status':'conditional_scenarios_ready','scenarios':scenarios,'rejected':rejected,'unconditionalProbabilityAvailable':False,'simulationsStarted':0,'noSourceVerificationUpgraded':True}
