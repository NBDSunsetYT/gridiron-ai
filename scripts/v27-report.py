"""Publish actual bounded V27 evidence/certification results, no new models."""
import sys,json,hashlib,gzip
from pathlib import Path
from collections import defaultdict
import numpy as np
import math
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from modeling.overnight_v20.state import read,digest
from modeling.iterative_learning import freeze_json
from modeling.integration_v22.datasets import protected
from modeling.dynamic_v24.completion.selection import paired_loss
OUT=ROOT/'artifacts/evidence-and-joint-v27'


def nba_time_valid(seconds,overtime):
    return math.isclose(seconds,2880+300*overtime,rel_tol=0,abs_tol=1e-7)


def run():
    start=read(OUT/'start.json')
    for p,sha in start['inheritedHashes'].items():
        if hashlib.sha256((ROOT/p).read_bytes()).hexdigest()!=sha:raise ValueError('Inherited forecast/model artifact changed: '+p)
    if digest(sorted(protected()))!=start['protectedIdsHash']:raise ValueError('Protected cohort changed')
    source=read(OUT/'source-cert-r4/results.json')['cases'];expanded=read(OUT/'nba-expanded-r6/results.json')['cases'];phase=read(OUT/'phase-clock-r3/results.json')['cases'];candidate=read(OUT/'nfl-conditional-clock-r7/results.json')['cases'];baseline=read(OUT/'baseline-r2/results.json')['cases']
    source_index={(c['sport'],c['gameId']):c for c in source}
    for c in expanded:source_index[(c['sport'],c['gameId'])]=c
    runtime_index={(c['sport'],c['gameId'],c['variant']):c for c in phase+expanded}
    counts={};certificates=[]
    for sport in ('NFL','CFB','NBA'):
        rows=[c for (s,g),c in source_index.items() if s==sport]
        counts[sport]={'sourceMatchupsAttempted':len(rows),'completeAccountingReplays':sum(c['replay'].get('completeAccountingReplay') is True for c in rows),'clockBoundaryConservation':sum(c['replay'].get('clock',{}).get('boundaryConservation') is True for c in rows) if sport!='NBA' else None,'officialMinuteBudgetsReconciled':sum(c['replay'].get('minuteBudgetReconciled') is True for c in rows) if sport=='NBA' else None,'sourceFailures':[{'gameId':c['gameId'],'reason':c['replay'].get('reason'),'countingDifferences':c['replay'].get('countingDifferences')} for c in rows if not c['replay'].get('completeAccountingReplay')]}
        for variant in ('reference','specialized'):
            cases=[c for c in runtime_index.values() if c['sport']==sport and c['variant']==variant and c['status']=='completed' and source_index[(sport,c['gameId'])]['replay'].get('completeAccountingReplay') is True]
            ids=sorted(c['gameId'] for c in cases);enough=len(ids)>=12
            model={'sport':sport,'sourcePolicy':'final_conditioned_historical_mechanics','inputPolicy':'final_conditioned_mechanics_only','variant':variant,'instanceModelHashes':{c['gameId']:c['modelHash'] for c in cases},'instanceConfigurations':{c['gameId']:c['modelConfiguration'] for c in cases},'sourceAuditHash':digest([source_index[(sport,c['gameId'])]['replay'] for c in cases]),'notRegistryApprovedSpecializedHeads':True}
            model['sha256']=digest(model)
            if sport=='NBA':
                checks={'regulation_clock_conservation':enough,'five_player_seconds':enough and all(source_index[(sport,c['gameId'])]['replay'].get('minuteBudgetReconciled') is True for c in cases),'scoring_accounting':enough and all(r['playerPointsEqualTeamPoints'] for c in cases for r in c['simulated']),'rebound_opportunities':enough and all(r['reboundable']==r['rebounded'] for c in cases for r in c['simulated']),'foul_substitution_rules':enough and all(c['mechanicalInvariantsPassed'] for c in cases),'overtime_accounting':enough and all(nba_time_valid(r['regulationAndOTSeconds'],r['overtimePeriods']) for c in cases for r in c['simulated'])}
            else:
                checks={'per_team_stat_reconciliation':enough and all(r['passingReceivingEqual'] for c in cases for r in c['simulated']),'regulation_clock_conservation':enough and all(r['regulationSeconds']==3600 and r['periodCharges']==[900]*4 for c in cases for r in c['simulated']),'possession_counting':False,'historical_play_count_realism':False,'historical_possession_realism':False,('nfl_timing_regime' if sport=='NFL' else 'ncaa_timing_regime'):False,'overtime_accounting':False}
            cert={'scope':'historical_full_game_validation','modelHash':model['sha256'],'boundModel':model,'independentGames':ids,'checks':checks,'mechanicalSubsetPassed':all(checks.values()),'sourceEditions':{c['gameId']:c['sourceVersion'] for c in cases},'generatedCaseHashes':{c['gameId']:digest(c) for c in cases},'sourceReplayEdition':'source-cert-r4 plus nba-expanded-r6','jointProbabilityValidation':None,'specializedMarginalDistributionCompatibility':False,'forecastEligible':False,'productionPromotionAllowed':False,'limitations':['Conditional event-accounting validation, not a pregame input certificate.','Source-mean adapters are not proof that registry winner distributions are compatible.','Rare-event coverage and independent probability validation remain incomplete.','Different seasons, engine versions or input snapshots cannot inherit this exact model hash.']}
            cert['sha256']=digest(cert);certificates.append(cert)
    timings=[]
    before={(c['gameId'],c['variant']):c for c in phase if c['sport']=='NFL' and c['status']=='completed'}
    for variant in ('reference','specialized'):
        group=[c for c in candidate if c['variant']==variant and c['status']=='completed'];old=np.array([np.mean([sum(r['teamPlays'].values()) for r in before[c['gameId'],variant]['simulated']]) for c in group]);new=np.array([np.mean([sum(r['teamPlays'].values()) for r in c['simulated']]) for c in group]);rows=[{'gameId':c['gameId'],'y':0} for c in group]
        paired=paired_loss(rows,old,new,loss='provided',alpha=.025,bootstraps=3000,seed=270027)
        timings.append({'variant':variant,'commonMatchups':len(group),'oldMeanPlays':float(old.mean()),'candidateMeanPlays':float(new.mean()),'pairedPlayCountShift':paired,'forecastAccuracyClaim':False,'meaning':'Change in conditional generated play volume, not error reduction or forecast superiority'})
    runs=[]
    for name in ('baseline-r2','phase-clock-r3','source-cert-r4','nba-expanded-r6','nfl-conditional-clock-r7'):
        result=read(OUT/name/'results.json');receipt=read(OUT/name/'receipt.json');runs.append({'run':name,'gamesByLeague':result['gamesByLeague'],'receipt':receipt,'protocolSHA256':digest(read(OUT/name/'protocol.json'))})
    partial=sum(read(p).get('games',0) for p in (OUT/'baseline-r1/cases').glob('*.json'))
    report={'version':27,'sourceReconciliation':counts,'certificates':certificates,'NFLClockExperiment':timings,'withheldClockCases':[{'gameId':c['gameId'],'variant':c['variant'],'reason':c.get('reason')} for c in candidate if c['status']!='completed'],'runs':runs,'partialAbortedPreparationRunCheckpointedGames':partial,'uncheckpointedNBAGamesBeforeSerializationFailure':4,'exactDefaultDisabledReplay':read(OUT/'default-clock-equivalence.json'),'newStrictFullGameForecasts':0,'newIndependentProbabilityEvaluationGames':0,'modelsPromoted':0,'allInheritedHashesVerified':True,'protectedCohortHashVerified':True,'preservedV26SourceSnapshots':start['inheritedHashes'],'scientificStopReason':'Source reconciliation, participant/rotation evidence, timing/pace realism and independent joint distribution validation remain incomplete. No unsupported gate is bypassed.'}
    report['reportRevision']='R2';report['clockComparisonToleranceSeconds']=1e-7
    report['supersedes']='R1 used exact float equality for the NBA clock report rather than the existing ledger roundoff tolerance; no model or simulation results changed.'
    freeze_json(ROOT/'docs/research/V27_MECHANICAL_RESULTS_R2.json.gz',report)
    print(json.dumps({'sourceReconciliation':{s:{k:v for k,v in r.items() if k!='sourceFailures'} for s,r in counts.items()},'mechanicalSubsetCertificatesPassed':sum(c['mechanicalSubsetPassed'] for c in certificates),'strictForecasts':0,'defaultReplayIdentical':report['exactDefaultDisabledReplay']['completeResultsIdentical']}))


if __name__=='__main__':run()
