"""Research gates fail closed; missing market observations remain null."""
import math
import numpy as np
from .fit import utc
VERSION='market-research-gates-18.0.0'
def gate1(tests,audit):
    failures=[]
    for key,minimum in [('tsPassed',753),('pythonPassed',200)]:
        if tests.get(key,0)<minimum:failures.append(key+'_below_required_count')
    if not tests.get('typecheckPassed') or not tests.get('allCommandsExitZero'):failures.append('required_command_failed')
    if audit.get('gamesCompleted')!=500 or not audit.get('allAccountingReconciled') or audit.get('simulatedCompleteGames')!=5000000:failures.append('500_game_accounting_audit_incomplete')
    return {'version':VERSION,'gate':1,'passed':not failures,'failures':failures,'metricDeltasAreReportedNotTuned':True}
def require_previous(gates,stage):
    if any(not gates.get(str(i),{}).get('passed') for i in range(1,stage)):raise ValueError('Every earlier gate must pass before stage '+str(stage))
def spread_gate(rows):
    valid=[];rejected=[]
    for r in rows:
        try:
            q=r['market']
            if q.get('product')!='sportsbook' or q.get('market')!='spread' or q.get('phase')!='closing' or q.get('verified') is not True:raise ValueError('Unverified closing sportsbook spread')
            if not q.get('book') or not q.get('sourceVersion') or not str(q.get('source','')).startswith('https://'):raise ValueError('Missing book/source provenance')
            if not q.get('capturedAt') or utc(q['capturedAt'])>=utc(r['eventAt']):raise ValueError('Closing capture time unavailable or after kickoff')
            if q.get('homeHandicap') is None or not all(math.isfinite(float(v)) for v in [q['homeHandicap'],r['modelHomeMargin']]):raise ValueError('Missing/nonfinite spread')
            valid.append((r['modelHomeMargin'],-q['homeHandicap']))
        except (ValueError,KeyError,TypeError) as e:rejected.append({'eventId':r.get('eventId'),'reason':str(e)})
    corr=float(np.corrcoef(np.array(valid).T)[0,1]) if len(valid)>=2 and all(np.std(v)>0 for v in zip(*valid)) else None
    return {'version':VERSION,'gate':2,'passed':corr is not None and corr>.80,'qualifiedGames':len(valid),'spreadCorrelation':corr,'requiredCorrelationStrictlyAbove':.80,'rejected':rejected,'CLV':None,'nextStageAllowed':corr is not None and corr>.80,'productionEligible':False}
