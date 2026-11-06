"""One predeclared opportunity experiment on exposed chronological diagnostics.

No more model families, no calibration sweep, no final-test tuning. Outcomes
are joined only after each conditional prediction is frozen. These downloaded
historical editions are NOT verified historical pregame editions.
"""
import sys,json,runpy,time,resource,hashlib
from pathlib import Path
from collections import defaultdict
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from modeling.accuracy_v25.opportunity_calendar import project,observed
from modeling.accuracy_v25.objectives import score_numerical
from modeling.dynamic_v24.completion.selection import paired_loss
from modeling.iterative_learning import freeze_json
from modeling.overnight_v20.state import digest

OUT=ROOT/'artifacts/accuracy-v26/calendar-r2'
STATS={'NFL':['passingAttempts','passingYards','carries','rushingYards','receptions','receivingYards'],
       'CFB':['passingAttempts','passingYards','carries','rushingYards','receptions','receivingYards'],
       'NBA':['minutes','points','rebounds','assists','fieldGoalAttempts','threePointersMade']}
HIGH={'passingAttempts':20,'passingYards':150,'carries':10,'rushingYards':40,'receptions':3,'receivingYards':40,
      'minutes':24,'points':15,'rebounds':6,'assists':4,'fieldGoalAttempts':10,'threePointersMade':2}


def run():
    original=runpy.run_path(str(ROOT/'scripts/v26-forecast.py'));manifest=json.load(open(ROOT/'artifacts/accuracy-v26/prospective-inputs-r1.json'))
    freeze_json(OUT/'protocol.json',{'hypothesis':'Appearance-conditioned marginals use unequal exposure denominators and cannot be combined as team budgets. Test common calendar exposure only when missing entries have explicit zero evidence.',
        'revisionReason':'Require requested-stat reconciliation as well as opportunity counts; distinguish NFL gross player passing from net team passing. Original r1 retained; no new model family or tuning.',
        'evidenceTier':'conditional_corrected_history','outcomeExposure':'All downloaded histories already exposed as prospective training inputs; NOT independent confirmation',
        'stats':STATS,'highVolumeStrata':HIGH,'minimumAppearanceGames':3,'evaluationIndices':[3,4],
        'newFits':0,'newMonteCarloGames':0,'protectedFinalAccess':False,'productionPromotionAllowed':False,
        'sourceManifestSHA256':hashlib.sha256((ROOT/'artifacts/accuracy-v26/prospective-inputs-r1.json').read_bytes()).hexdigest(),
        'codeSHA256':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),ROOT/'modeling/accuracy_v25/opportunity_calendar.py',ROOT/'scripts/v26-forecast.py']}})
    raw={};games={}
    for r in manifest['sources']:
        if r['kind']=='history' and 'error' not in r:
            d=original['body'](r['receipt']);raw[(r['sport'],r['eventId'])]=d;games[(r['sport'],r['eventId'])]=original['normalized'](d,r['sport'])
    graded=[];pending=[];seen=set();reconciliation=[]
    for target in manifest['targets']:
        sport=target['sport']
        for team,ids in target['historyIds'].items():
            history=sorted([games[(sport,g)] for g in ids],key=lambda g:g['at']);owned={g['eventId']:raw[(sport,g['eventId'])] for g in history}
            for index in (3,4):
                if index>=len(history):continue
                validation=history[index];train=history[:index]
                if (sport,team,validation['eventId']) in seen:continue
                seen.add((sport,team,validation['eventId']))
                assert all(g['at']<validation['at'] for g in train)
                players=sorted({p for g in train for p in g['teams'][team]['players']})
                frozen=[]
                for stat in STATS[sport]:
                    for player in players:
                        p=project(train,owned,sport,team,player,stat)
                        if p:frozen.append({'sport':sport,'gameId':validation['eventId'],'team':team,'player':player,'stat':stat,'at':validation['at'],'trainingGameIds':[g['eventId'] for g in train],'trainingThrough':train[-1]['at'],'projection':p})
                key=sport+'-'+team+'-'+validation['eventId']
                freeze_json(OUT/'forecasts'/(key+'.json'),{'scope':'exposed_conditional_diagnostic_not_pregame_forecast','predictions':frozen})
                for row in frozen:
                    y,proof=observed(validation,owned[validation['eventId']],sport,team,row['player'],row['stat'])
                    if y is None:pending.append({k:row[k] for k in ('sport','gameId','team','player','stat')}|{'reason':proof});continue
                    p=row['projection'];before=score_numerical([y],[p['reference']],[p['referenceDistribution']]);after=score_numerical([y],[p['candidate']],[p['candidateDistribution']])
                    graded.append(row|{'y':y,'actualProof':proof,'referenceScores':before,'candidateScores':after,
                                       'highVolume':p['reference']>=HIGH[row['stat']],
                                       'referenceZeroBrier':(np.mean(np.array(p['referenceDistribution'])==0)-int(y==0))**2,
                                       'candidateZeroBrier':(np.mean(np.array(p['candidateDistribution'])==0)-int(y==0))**2})
    summaries=[]
    for sport in STATS:
        for stat in STATS[sport]:
            group=[r for r in graded if r['sport']==sport and r['stat']==stat]
            if not group:continue
            y=np.array([r['y'] for r in group]);a=np.array([r['projection']['reference'] for r in group]);b=np.array([r['projection']['candidate'] for r in group])
            def metrics(points,side):
                e=points-y
                return {'mae':float(np.mean(abs(e))),'rmse':float(np.sqrt(np.mean(e*e))),'bias':float(np.mean(e)),
                        'crps':float(np.mean([r[side+'Scores']['crps'] for r in group])),
                        'interval90Coverage':float(np.mean([r[side+'Scores']['intervals']['0.9']['coverage'] for r in group])),
                        'zeroEventBrier':float(np.mean([r[side+'ZeroBrier'] for r in group]))}
            delta=paired_loss(group,a,b,loss='absolute',alpha=.05/18,bootstraps=3000,seed=260026)
            high=[i for i,r in enumerate(group) if r['highVolume']]
            summary={'sport':sport,'stat':stat,'games':len({r['gameId'] for r in group}),'observations':len(group),
                     'reference':metrics(a,'reference'),'candidate':metrics(b,'candidate'),'pairedGameMAE':delta,
                     'highVolume':{'observations':len(high),'referenceMAE':float(np.mean(abs(a[high]-y[high]))) if high else None,'candidateMAE':float(np.mean(abs(b[high]-y[high]))) if high else None},
                     'strictIndependentGames':0,'promotionEligible':False,'decision':'diagnostic_only_evidence_and_sample_gates_not_passed'}
            summaries.append(summary)
    report={'scope':'new_structural_exposed_conditional_diagnostic','summaries':summaries,
            'uniqueGamesByLeague':{s:len({r['gameId'] for r in graded if r['sport']==s}) for s in STATS},
            'observations':len(graded),'ungradedMissingActuals':pending,'modelsFit':0,'newStrictForecasts':0,
            'newIndependentConfirmationGames':0,'MonteCarloGames':0,'modelsPromoted':0,
            'marketThresholdsVerified':0,'marketLineBrier':None,'moneylineBrier':None,'logLoss':None,
            'classificationWarning':'Historical source editions were captured after these games; predictions are chronological diagnostics only, not historical pregame evidence.',
            'sourceAndForecastRecordsSaved':True}
    freeze_json(OUT/'graded-observations.json.gz',graded)
    freeze_json(OUT/'results.json',report);freeze_json(ROOT/'docs/research/V26_CALENDAR_RESULTS_R2.json',report)
    print(json.dumps({'games':report['uniqueGamesByLeague'],'observations':len(graded),'categories':len(summaries),'newIndependentGames':0,'promotions':0}),flush=True)
    for s in summaries:print(json.dumps({'sport':s['sport'],'stat':s['stat'],'games':s['games'],'observations':s['observations'],'MAE':[s['reference']['mae'],s['candidate']['mae']],'highVolume':s['highVolume'],'CI':s['pairedGameMAE']['CI95']}),flush=True)


if __name__=='__main__':
    start=time.monotonic();cpu=time.process_time();run();print(json.dumps({'cpuSeconds':time.process_time()-cpu,'wallSeconds':time.monotonic()-start,'peakRssKiB':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}),flush=True)
