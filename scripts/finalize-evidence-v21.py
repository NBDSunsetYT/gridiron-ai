"""Export aggregate research evidence, with no upstream datasets in Git."""
import sys,json,gzip,pickle,hashlib,platform,importlib.metadata
from pathlib import Path
from collections import defaultdict,Counter
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from modeling.evidence_v21.io import OUT
from modeling.evidence_v21.runtime import verify_parent
from modeling.evidence_v21.protection import protected_ids,assert_unexposed
from modeling.evidence_v21.quality import record
from modeling.overnight_v20.state import read,atomic
from modeling.iterative_learning import freeze_json,digest
def unpack(p):return json.loads(gzip.decompress(p.read_bytes()))
def main():
 verify_parent();p=read(OUT/'protocol-final.json');reserved=protected_ids(p);finals={g['id'] for gs in p['sealedFinal'].values() for g in gs};confirmation=reserved-finals;counts=defaultdict(lambda:{'games':set(),'observations':0});batches=[];quality=[];audits=[];seen=set()
 roots=[('components',[f.parent for f in sorted((OUT/'components').glob('*/grades.json.gz'))]),*[(r,[f.parent for f in sorted((OUT/r).glob('*/grades.json.gz'))]) for r in ['independent','season-confirmation','source-repair','clean-confirmation']]]
 for batch,folders in roots:
  totals=defaultdict(lambda:{'games':set(),'observations':0})
  for folder in folders:
   grades=unpack(folder/'grades.json.gz');sport=folder.name.split('-')[0];snapshot=unpack(folder/'forecasts.json.gz');gids={r['gameId'] for r in grades};duplicates=seen&gids
   if duplicates:raise ValueError('Duplicate evaluation games across batches')
   seen|=gids;assert_unexposed(gids,reserved);totals[sport]['games']|=gids;totals[sport]['observations']+=len(grades);counts[sport]['games']|=gids;counts[sport]['observations']+=len(grades);ids=set(snapshot.get('trainingGameIds',snapshot.get('trainingIds',[])))
   if batch in ['source-repair','clean-confirmation']:
    m=pickle.loads((folder/'models.pickle').read_bytes());ids={i for mm in m.values() for i in mm['trainingIds']}
   item={'batch':batch,'sport':sport,'trainingGames':len(ids),'sealedTrainingOverlap':len(ids&finals),'lockedConfirmationTrainingOverlap':len(ids&confirmation),'protectedTrainingCheckPassed':not bool(ids&reserved),'promotionEvidenceEligible':False,'protocolTier':'conditional_corrected_history_component'};audits.append(item)
   if ids&finals:raise ValueError('Sealed final game in historical model fit')
   if batch=='clean-confirmation':assert_unexposed(ids,reserved)
   # Only facts originally available to this batch are used in its audit.
   facts=unpack(OUT/'evidence/NBA-expanded.json.gz')['facts'] if sport=='NBA' and batch=='components' else unpack(OUT/'evidence/NFL-primary-facts.json.gz') if sport=='NFL' and batch=='components' else []
   for g in snapshot['games']:
    ownership=defaultdict(set)
    for r in snapshot['rows']:
     if r['gameId']==g['id']:ownership[r['player']].add(r['team'])
    quality.append({**record(g,facts,digest(p['sourceFiles']),consistency={'ownership':all(len(ts)==1 for ts in ownership.values())}),'batch':batch})
    for pid,teams in ownership.items():
     for t in teams:quality.append({**record(g,facts,digest(p['sourceFiles']),pid,t,{'ownership':len(teams)==1}),'batch':batch})
  batches.append({'batch':batch,'leagues':{s:{'games':len(v['games']),'observations':v['observations']} for s,v in totals.items()}})
 clean=read(OUT/'clean-confirmation/results.json');primary={}
 for sport,stat,family,ref in [('NFL','passingYards','raw_hurdle','raw_rolling5'),('CFB','passingYards','box_hurdle','raw_hurdle'),('NBA','minutes','lineup_state_minutes','raw_hurdle')]:primary[sport]={'statistic':stat,'candidate':family,'reference':ref,**clean['leagues'][sport]['categories'][stat][family][ref]}
 from importlib.machinery import SourceFileLoader
 metrics=SourceFileLoader('v21_final_metrics',str(ROOT/'scripts/research-independent-v21.py')).load_module();volume={};worst={}
 for sport,stat,family,ref,op,minimum in [('NFL','passingYards','raw_hurdle','raw_rolling5','passingAttempts',10),('CFB','passingYards','box_hurdle','raw_hurdle','passingAttempts',10),('NBA','minutes','lineup_state_minutes','raw_hurdle','minutes',20),('NBA','rebounds','raw_hurdle','raw_rolling5','minutes',20)]:
  rows=unpack(OUT/'clean-confirmation'/sport/'grades.json.gz');prior={(r['gameId'],r['team'],r['player']):r['predictions'].get('raw_rolling5') for r in rows if r['stat']==op};use=[r for r in rows if r['stat']==stat and isinstance(prior.get((r['gameId'],r['team'],r['player'])),(int,float)) and prior[(r['gameId'],r['team'],r['player'])]>=minimum];volume[sport+':'+stat]={'preforcastOpportunityThreshold':minimum,'opportunityStatistic':op,'selectionUsesCurrentOutcome':False,'comparison':metrics.paired(use,family,ref)};rr=[r for r in rows if r['stat']==stat and family in r['predictions']];worst[sport+':'+stat]=[{'eventId':r['gameId'],'playerId':r['player'],'prediction':r['predictions'][family],'actual':r['actual'],'absoluteError':abs(r['predictions'][family]-r['actual']),'injuryAndLineupAtPrediction':'unknown_or_partial; no causal injury attribution asserted'} for r in sorted(rr,key=lambda r:abs(r['predictions'][family]-r['actual']),reverse=True)[:5]]
 clock=read(OUT/'clock/reports/clock-accounting-r5/results.json');receipt={f.stem:read(f) for f in (OUT/'receipts').glob('*.json')};runtime=read(OUT/'runtime/state.json');parent=read(ROOT/'artifacts/overnight-v20/runtime/state.json');env={'python':platform.python_version(),'platform':platform.platform(),'dependencies':{k:importlib.metadata.version(k) for k in ['numpy','scipy','scikit-learn','pyarrow','pypdf','threadpoolctl']}};atomic(OUT/'environment.json',env)
 summary={'version':21,'generatedAt':datetime.now(timezone.utc).isoformat(),'branch':'research/overnight-v21','productionChanged':False,'promotions':[],'strictPregameEligibleGames':0,'newCompleteGameSimulations':0,'uniqueForecastGames':sum(len(v['games']) for v in counts.values()),'playerStatObservations':sum(v['observations'] for v in counts.values()),'leagues':{s:{'games':len(v['games']),'observations':v['observations']} for s,v in counts.items()},'batches':batches,'cleanPrimaryComparisons':primary,'clockComponent':{k:clock[k] for k in ['validationGames','validationBlocks','trainingGames','models','independentGamebooks']},'availabilityRecovery':read(OUT/'evidence/availability-recovery-availability-r5-coverage.json'),'historicalBoxRepair':read(OUT/'source-repair/input-coverage.json'),'protection':{'sealedFinalGames':len(finals),'lockedConfirmationGames':len(confirmation),'allParentChecksumsVerified':True,'earlierFitsWithLockedTrainingReuse':[a for a in audits if a['lockedConfirmationTrainingOverlap']],'cleanBatchProtectedTrainingOverlap':0,'meaning':'Earlier new-season NFL/NBA fits reused older confirmation histories. They remain diagnostics, not promotion evidence. Clean confirmation excludes both cohorts.'},'quality':{'records':len(quality),'tiers':dict(Counter(q['tier'] for q in quality)),'unknownMeansHealthy':False},'resources':{'measuredV21JobCpuSeconds':sum(r['cpuSeconds'] for r in receipt.values()),'measuredV21JobWallSeconds':sum(r['activeSeconds'] for r in receipt.values()),'maximumJobPeakRssKiB':max(r['peakRssKiB'] for r in receipt.values()),'inheritedMeasuredActiveSeconds':parent['measuredActiveSeconds'],'cumulativeMeasuredActiveSeconds':runtime['measuredActiveSeconds'],'cumulativeSafetyWallCharges':runtime['setupSafetyChargeSeconds'],'cumulativeCpuLedger':runtime['completedCpuSeconds'],'cpuLedgerIncludesConservativePreflightReservation':True,'unmeasuredEngineeringCpuIncluded':False,'maximumCumulativeSeconds':36000,'hostedSimulationCalls':0},'stopReason':'Registered component hypotheses and clean confirmation completed; strict historical injury/lineup/publication and complete-game clock/model-uncertainty gates remain unresolved. No overall predictive superiority established. No repeated sealed test optimization.','probabilityAndTeamScoreMetrics':None,'probabilityReason':'No new fully qualified joint-game forecasts or verified historical market thresholds; no invented Brier/log-loss/calibration/interval claims.','environment':env}
 summary['higherPregameVolumeSlices']=volume;summary['largestErrors']=worst;freeze_json(OUT/'diagnostics/final-quality.json.gz',quality);atomic(OUT/'diagnostics/protected-training-audit.json',audits);atomic(OUT/'final-summary.json',summary)
 public=ROOT/'docs/reports';public.mkdir(exist_ok=True);atomic(public/'overnight-v21-results.json',summary)
 for name in ['independent-protocol.json','season-confirmation-protocol.json','source-repair-protocol.json','clean-confirmation-protocol.json']:atomic(public/('overnight-v21-'+name),read(OUT/name))
 atomic(OUT/'accuracy-first-pause.json',{'version':21,'originalV20PauseChanged':False,'fullGameForecastsPermitted':False,'componentRepairsValidated':True,'missing':['Complete original pregame injury/lineup/participation evidence','Verified original publication of historical statistics/weather where required','Unresolved CFB administrative clock/state sequences','Validated model uncertainty and joint probability/interval performance'],'protectedHoldoutsExcludedFromFutureTraining':True,'stopReason':summary['stopReason']});print(json.dumps({'games':summary['leagues'],'observations':summary['playerStatObservations'],'protectedAudits':len(audits),'strictGames':0},indent=2))
if __name__=='__main__':main()
