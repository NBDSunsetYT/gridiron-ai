"""Descriptive chronological comparisons; never alters a forecast or model."""
from collections import defaultdict
import math
import numpy as np
from ..structural_v18.models import error_metrics
from ..calibration_research import metrics,paired_interval

def summarize(grades):
    players=defaultdict(list)
    for g in grades:
        for r in g['players']:players[r['stat']].append((g['gameId'],r))
    bs=[g for g in grades if not g['ties']]
    return {'games':len(grades),'moneyline':metrics([g['probability'] for g in bs],[g['truth'] for g in bs]) if bs else None,'teamScore':error_metrics([r['actual'] for g in grades for r in g['score']],[r['mean'] for g in grades for r in g['score']]) if grades else None,'players':{s:{**error_metrics([r['actual'] for gid,r in rs],[r['mean'] for gid,r in rs]),'games':len({gid for gid,r in rs}),'players':len({r['id'] for gid,r in rs}),'coverage90':float(np.mean([r['coverage']['0.9']['covered'] for gid,r in rs])),'meanCRPS':float(np.mean([r['crps'] for gid,r in rs]))} for s,rs in players.items()}}

def compare(reference,candidate,sport):
    pairs=[(reference[g],candidate[g]) for g in sorted(set(reference)&set(candidate))];primary='rebounds' if sport=='NBA' else 'passingYards';before=[];after=[];allbefore=[];allafter=[]
    for a,b in pairs:
        aa={r['id']:r for r in a['players'] if r['stat']==primary and not r['knownOutAtCutoff']};bb={r['id']:r for r in b['players'] if r['stat']==primary and not r['knownOutAtCutoff']};keys=set(aa)&set(bb)
        if keys:before.append(np.mean([abs(aa[k]['error']) for k in keys]));after.append(np.mean([abs(bb[k]['error']) for k in keys]));allbefore.extend(abs(aa[k]['error']) for k in keys);allafter.extend(abs(bb[k]['error']) for k in keys)
    delta=paired_interval(before,after,seed=20020) if before else None;rb=metrics([a['probability'] for a,b in pairs if not a['ties']],[a['truth'] for a,b in pairs if not a['ties']]) if pairs else None;cb=metrics([b['probability'] for a,b in pairs if not a['ties']],[b['truth'] for a,b in pairs if not a['ties']]) if pairs else None;score_delta=float(np.mean([abs(r['error']) for a,b in pairs for r in b['score']])-np.mean([abs(r['error']) for a,b in pairs for r in a['score']])) if pairs else None
    meaningful=bool(delta and delta['bootstrap95'][1]<0 and np.mean(after)<=.99*np.mean(before) and cb['brier']<=rb['brier'] and cb['logLoss']<=rb['logLoss'] and score_delta<=0)
    return {'primary':primary,'pairedGames':len(before),'primaryDelta':delta,'referenceMAE':float(np.mean(allbefore)) if allbefore else None,'candidateMAE':float(np.mean(allafter)) if allafter else None,'brierDelta':cb['brier']-rb['brier'] if cb else None,'logLossDelta':cb['logLoss']-rb['logLoss'] if cb else None,'scoreMAEDelta':score_delta,'meaningfulConditionalImprovement':meaningful,'qualifiedForProductionReview':False,'reason':'Conditional corrected-history results. Complete original pregame publication/lineup evidence and minimum 200 independent-game gate remain unsatisfied.'}
