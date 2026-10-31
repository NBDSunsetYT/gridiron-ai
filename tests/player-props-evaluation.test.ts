import {afterEach,describe,it,expect,vi} from 'vitest';
import {PROP_EVALUATION_PROTOCOL,comparePropThreshold,resolvePropOutcome,auditPropPrediction,scorePropObservations,evaluatePropHistory,gameBlockInterval,propProbabilityMetrics,fitPropCalibrator,validatePropCandidate,approvePropCalibrator,applyPropCalibration,propModelDrift,type FrozenPropPrediction,type VerifiedPropResolution,type PropStatContract,type FinalPlayerStatistic} from '../lib/player-props/evaluation';

// SYNTHETIC statistical boundaries only. No fixture is published as NFL data.
const prediction=(overrides:Partial<FrozenPropPrediction>={}):FrozenPropPrediction=>({id:'SYNTHETIC-PRED',contractId:'SYNTHETIC-CONTRACT',gameId:'SYNTHETIC-GAME',playerId:'SYNTHETIC-PLAYER',category:'receivingYards',threshold:64.5,operator:'gt',rawProbability:.7,calibratedProbability:null,marketProbability:.55,modelVersion:'SYNTHETIC-PBP-V6',inputVersion:'SYNTHETIC-FROZEN-HASH',predictedAt:'2026-06-01T12:00:00Z',archivedAt:'2026-06-01T12:00:01Z',eventStart:'2026-06-01T18:00:00Z',dataAvailableAt:'2026-06-01T11:59:59Z',...overrides});
const resolution=(overrides:Partial<VerifiedPropResolution>={}):VerifiedPropResolution=>({id:'SYNTHETIC-RESOLUTION',predictionId:'SYNTHETIC-PRED',status:'yes',resolvedAt:'2026-06-01T23:00:00Z',sourceUrl:'https://example.invalid/SYNTHETIC-final-statistics',sourceVersion:'SYNTHETIC-SOURCE-V1',verifiedFinal:true,...overrides});
const now=()=>new Date('2026-07-01T00:00:00Z');
const contract:PropStatContract={gameId:'SYNTHETIC-GAME',playerId:'SYNTHETIC-PLAYER',category:'receivingYards',threshold:64.5,operator:'gt',rulesVerified:true,dnpRule:'void',includesOvertime:true,fullGame:true};
const stat:FinalPlayerStatistic={gameId:contract.gameId,playerId:contract.playerId,category:contract.category,value:65,gameFinal:true,fullGame:true,includesOvertime:true,participated:true,checkedAt:'2026-06-01T23:00:00Z',sourceUrl:'https://example.invalid/SYNTHETIC-final-statistics',sourceVersion:'SYNTHETIC-SOURCE-V1',verified:true};
afterEach(()=>{vi.useRealTimers();});

describe('Exact prop research settlement and immutable audit boundaries',()=>{
 it('honors strict and inclusive thresholds without treating equality as a sportsbook push',()=>{
  expect(comparePropThreshold(65,64.5,'gt')).toBe(true);expect(comparePropThreshold(65,65,'gt')).toBe(false);expect(comparePropThreshold(65,65,'gte')).toBe(true);expect(comparePropThreshold(65,65,'lte')).toBe(true);expect(comparePropThreshold(65,65,'lt')).toBe(false);expect(comparePropThreshold(65,65,'eq')).toBe(true);
  expect(resolvePropOutcome({...contract,threshold:65},stat)).toMatchObject({status:'no',observedValue:65,exchangeSettlementVerified:false});
 });
 it('does not turn missing statistics or unknown player participation into zero',()=>{
  expect(resolvePropOutcome(contract,{...stat,value:null}).status).toBe('unresolved');expect(resolvePropOutcome(contract,{...stat,participated:null,value:0}).status).toBe('unresolved');expect(resolvePropOutcome(contract,{...stat,participated:false,value:null}).status).toBe('void');
  expect(resolvePropOutcome({...contract,dnpRule:'settle_zero'},{...stat,participated:false,value:null})).toMatchObject({status:'no',observedValue:0});
 });
 it('withholds mismatched player, statistic, game, overtime and unverified rule/source combinations',()=>{
  for(const changed of [{playerId:'SYNTHETIC-OTHER'},{gameId:'SYNTHETIC-OTHER'},{category:'rushingYards'},{gameFinal:false},{verified:false},{includesOvertime:false},{sourceUrl:'http://example.invalid/SYNTHETIC'}])expect(resolvePropOutcome(contract,{...stat,...changed}).status).toBe('unresolved');
  expect(resolvePropOutcome({...contract,includesOvertime:false},stat).status).toBe('unresolved');expect(resolvePropOutcome({...contract,rulesVerified:false},stat).status).toBe('unresolved');expect(resolvePropOutcome(contract,{...stat,exceptionalSettlementUnresolved:true}).status).toBe('unresolved');
 });
 it('only marks a provider void where it is explicitly supplied as verified evidence',()=>{expect(resolvePropOutcome(contract,{...stat,providerVoided:true})).toMatchObject({status:'void',exchangeSettlementVerified:true});expect(resolvePropOutcome(contract,{...stat,providerVoided:true,verified:false}).status).toBe('unresolved');});
 it('excludes late archives, look-ahead inputs, retrospective estimates and missing timezone information',()=>{
  expect(auditPropPrediction(prediction({archivedAt:'2026-06-01T18:00:00Z'}),now())).toContain('not_archived_before_kickoff');expect(auditPropPrediction(prediction({dataAvailableAt:'2026-06-01T12:01:00Z'}),now())).toContain('look_ahead_inputs');expect(auditPropPrediction(prediction({retrospective:true}),now())).toContain('retrospective_import');expect(auditPropPrediction(prediction({predictedAt:'2026-06-01T12:00:00'}),now())).toContain('missing_timezone_aware_timestamps');
 });
 it('does not present voided or unverified outcomes as successful historical predictions',()=>{
  const result=evaluatePropHistory([prediction()],[resolution({status:'void'})],now());expect(result.eligibleResolved).toBe(0);expect(result.overall.raw).toBeNull();expect(result.excludedCounts.void_not_binary).toBe(1);expect(evaluatePropHistory([prediction()],[resolution({verifiedFinal:false})],now()).excludedCounts.unverified_final_source).toBe(1);
 });
 it('selects the last pre-kickoff snapshot without looking at outcomes and does not count YES/NO twice',()=>{
  const early=prediction({id:'SYNTHETIC-EARLY',rawProbability:.2}),latest=prediction({id:'SYNTHETIC-LATEST',predictedAt:'2026-06-01T13:00:00Z',archivedAt:'2026-06-01T13:00:01Z',side:'NO',rawProbability:.3}),late=prediction({id:'SYNTHETIC-LATE',predictedAt:'2026-06-01T18:10:00Z',archivedAt:'2026-06-01T18:10:01Z',rawProbability:1});
  const result=scorePropObservations([late,early,latest],[resolution({predictionId:early.id,status:'no'}),resolution({id:'SYNTHETIC-RES-2',predictionId:latest.id,status:'yes'})],now());expect(result.rows).toHaveLength(1);expect(result.rows[0]).toMatchObject({predictionId:latest.id,rawProbability:.7,outcome:1});expect(result.exclusions.map(r=>r.reason)).toContain('not_archived_before_kickoff');expect(result.exclusions.map(r=>r.reason)).toContain('earlier_snapshot_same_contract_model');
 });
 it('preserves probabilities while accepting only an explicit append-only correction chain',()=>{
  const frozen=Object.freeze(prediction()),first=resolution({status:'no'}),corrected=resolution({id:'SYNTHETIC-CORRECTION',previousResolutionId:first.id,status:'yes',resolvedAt:'2026-06-02T00:00:00Z',sourceVersion:'SYNTHETIC-CORRECTED-V2'});
  expect(scorePropObservations([frozen],[first,corrected],now()).rows[0].outcome).toBe(1);expect(frozen.rawProbability).toBe(.7);
  const conflicting={...corrected,previousResolutionId:undefined};const bad=scorePropObservations([frozen],[first,conflicting],now());expect(bad.rows).toHaveLength(0);expect(bad.exclusions[0].reason).toBe('ambiguous_resolution_correction');
 });
 it('rejects duplicate snapshot identities and changed settlement hashes',()=>{
  const duplicates=scorePropObservations([prediction(),prediction({rawProbability:.9})],[resolution()],now());expect(duplicates.rows).toHaveLength(0);expect(duplicates.exclusions.every(r=>r.reason==='duplicate_prediction_identity')).toBe(true);
  expect(scorePropObservations([prediction({rulesHash:'SYNTHETIC-RULE-A'})],[resolution({rulesHash:'SYNTHETIC-RULE-B'})],now()).exclusions[0].reason).toBe('settlement_rules_changed_or_missing');
 });
});

describe('Prospective prop metrics and honest uncertainty',()=>{
 it('calculates Brier/log loss from actual outcomes, including finite log loss at probability endpoints',()=>{
  const metric=propProbabilityMetrics([{gameId:'SYNTHETIC-A',p:.8,y:1},{gameId:'SYNTHETIC-B',p:.3,y:0}])!;expect(metric.brier).toBeCloseTo((.04+.09)/2,12);expect(metric.logLoss).toBeCloseTo((-Math.log(.8)-Math.log(.7))/2,12);expect(metric.brierInterval95).toBeNull();expect(metric.calibration.reduce((n,b)=>n+b.n,0)).toBe(2);expect(Number.isFinite(propProbabilityMetrics([{gameId:'SYNTHETIC-A',p:0,y:1}])!.logLoss)).toBe(true);expect(propProbabilityMetrics([])).toBeNull();
 });
 it('compares the market on the same contracts and leaves unavailable calibration null',()=>{
  const a=prediction(),b=prediction({id:'SYNTHETIC-B',contractId:'SYNTHETIC-B',rawProbability:.2,marketProbability:null,calibratedProbability:.3});const result=evaluatePropHistory([a,b],[resolution(),resolution({id:'SYNTHETIC-RB',predictionId:b.id,status:'no'})],now());expect(result.overall.raw?.n).toBe(2);expect(result.overall.calibrated).toBeNull();expect(result.overall.marketComparison.commonSampleSize).toBe(1);expect(result.overall.marketComparison.rawOnCommon?.n).toBe(1);expect(result.overall.marketComparison.marketOnCommon?.n).toBe(1);expect(result.byCategory.receivingYards.n).toBe(2);expect(result.windows.days7.raw).toBeNull();
 });
 it('does not mistake many correlated props in one game for independent game coverage',()=>{
  const values=Array.from({length:1000},(_,i)=>({gameId:'SYNTHETIC-ONE-GAME',value:i%2}));expect(gameBlockInterval(values)).toBeNull();
  const blocks=Array.from({length:20},(_,i)=>({gameId:'SYNTHETIC-GAME-'+i,value:i%2}));const one=gameBlockInterval(blocks,2026,500),two=gameBlockInterval(blocks,2026,500);expect(one).toEqual(two);expect(one![0]).toBeLessThan(.5);expect(one![1]).toBeGreaterThan(.5);
 });
 it('normalizes timezone offsets before chronological grouping',()=>{
  const p=prediction({eventStart:'2026-06-01T14:00:00-04:00'});expect(scorePropObservations([p],[resolution()],now()).rows[0].eventStart).toBe('2026-06-01T18:00:00.000Z');
 });
});

function cohort(start:string,games=200,prefix='SYNTHETIC-TRAIN'){
 const probabilities=[.3,.4,.5,.6,.7],successRates=[.1,.2,.5,.8,.9],predictions:FrozenPropPrediction[]=[],resolutions:VerifiedPropResolution[]=[];
 for(let game=0;game<games;game++)for(let i=0;i<5;i++){
  const at=Date.parse(start)+game*3600000,id=`${prefix}-${game}-${i}`,eventStart=new Date(at).toISOString(),predictedAt=new Date(at-3600000).toISOString(),resolvedAt=new Date(at+4*3600000).toISOString();
  predictions.push(prediction({id,contractId:id,gameId:`${prefix}-GAME-${game}`,playerId:`SYNTHETIC-PLAYER-${i}`,rawProbability:probabilities[i],marketProbability:successRates[i],predictedAt,archivedAt:predictedAt,eventStart,dataAvailableAt:new Date(at-7200000).toISOString()}));
  resolutions.push(resolution({id:id+'-RES',predictionId:id,status:game%10<successRates[i]*10?'yes':'no',resolvedAt}));
 }
 return{predictions,resolutions};
}
const training=()=>cohort('2026-04-01T12:00:00Z'),holdout=()=>cohort('2026-06-02T12:00:00Z',200,'SYNTHETIC-HOLDOUT');

describe('Controlled chronological calibration and model promotion',()=>{
 it('withholds calibration when there is no approved matching artifact or sufficient history',()=>{
  expect(applyPropCalibration(.6,null,{category:'receivingYards',modelVersion:'SYNTHETIC-PBP-V6',predictedAt:'2026-07-01T00:00:00Z'})).toBeNull();
  expect(()=>fitPropCalibrator([prediction()],[resolution()],{category:'receivingYards',modelVersion:'SYNTHETIC-PBP-V6',asOf:'2026-07-01T00:00:00Z'})).toThrow(/Insufficient prospective evidence/);
 });
 it('fits a real monotone isotonic candidate from only pre-cutoff observations, then waits for subsequent games',()=>{
  vi.useFakeTimers();vi.setSystemTime(new Date('2026-06-01T00:00:00Z'));const train=training();const artifact=fitPropCalibrator(train.predictions,train.resolutions,{category:'receivingYards',modelVersion:'SYNTHETIC-PBP-V6',asOf:'2026-06-01T00:00:00Z'});expect(artifact.status).toBe('candidate');expect(artifact.trainingSampleSize).toBe(1000);expect(artifact.trainingGames).toBe(200);expect(artifact.blocks!.map(row=>row.probability)).toEqual([.1,.2,.5,.8,.9]);expect(applyPropCalibration(.4,artifact,{category:artifact.category,modelVersion:artifact.modelVersion,predictedAt:'2026-06-01T00:00:00Z'})).toBeNull();
  const before=validatePropCandidate(artifact,train.predictions,train.resolutions,new Date('2026-06-01T00:00:00Z'));expect(before.n).toBe(0);expect(before.eligibleForPromotion).toBe(false);expect(()=>approvePropCalibrator(artifact,before)).toThrow(/remains unapproved/);
 });
 it('uses a separate subsequent holdout and paired game blocks before approving a genuinely improved calibrator',()=>{
  vi.useFakeTimers();vi.setSystemTime(new Date('2026-06-01T00:00:00Z'));const train=training(),test=holdout(),artifact=fitPropCalibrator(train.predictions,train.resolutions,{category:'receivingYards',modelVersion:'SYNTHETIC-PBP-V6',asOf:'2026-06-01T00:00:00Z'});
  vi.setSystemTime(now());const validation=validatePropCandidate(artifact,[...train.predictions,...test.predictions],[...train.resolutions,...test.resolutions],now());expect(validation.n).toBe(200);expect(validation.games).toBe(40);expect(validation.eligibleForPromotion).toBe(true);expect(validation.brierDifferenceInterval95![1]).toBeLessThan(0);expect(validation.logLossDifferenceInterval95![1]).toBeLessThan(0);expect(validation.marketAdvantageEstablished).toBe(false);const approved=approvePropCalibrator(artifact,validation);expect(approved.protocol).toBe(PROP_EVALUATION_PROTOCOL);expect(applyPropCalibration(.4,approved,{category:approved.category,modelVersion:approved.modelVersion,predictedAt:'2026-07-02T00:00:00Z'})).toBeCloseTo(.2);expect(artifact.status).toBe('candidate');
  expect(applyPropCalibration(.4,approved,{category:'rushingYards',modelVersion:approved.modelVersion,predictedAt:'2026-07-02T00:00:00Z'})).toBeNull();expect(applyPropCalibration(.4,approved,{category:approved.category,modelVersion:'UNRELATED-HOME-WIN-MODEL',predictedAt:'2026-07-02T00:00:00Z'})).toBeNull();expect(applyPropCalibration(.4,approved,{category:approved.category,modelVersion:approved.modelVersion,predictedAt:'2026-06-10T00:00:00Z'})).toBeNull();expect(applyPropCalibration(.99,approved,{category:approved.category,modelVersion:approved.modelVersion,predictedAt:'2026-07-02T00:00:00Z'})).toBeNull();
 });
 it('fits predeclared regularized Platt candidates without automatically promoting them',()=>{
  vi.useFakeTimers();vi.setSystemTime(new Date('2026-06-01T00:00:00Z'));const train=training();const candidate=fitPropCalibrator(train.predictions,train.resolutions,{category:'receivingYards',modelVersion:'SYNTHETIC-PBP-V6',asOf:'2026-06-01T00:00:00Z',method:'platt'});expect(candidate.slope).toBeGreaterThan(1);expect(Number.isFinite(candidate.intercept)).toBe(true);expect(candidate.status).toBe('candidate');
 });
 it('freezes the first40 future game blocks rather than peeking at favorable later outcomes',()=>{
  vi.useFakeTimers();vi.setSystemTime(new Date('2026-06-01T00:00:00Z'));const train=training(),test=holdout(),artifact=fitPropCalibrator(train.predictions,train.resolutions,{category:'receivingYards',modelVersion:'SYNTHETIC-PBP-V6',asOf:'2026-06-01T00:00:00Z'});vi.setSystemTime(now());
  const initial=validatePropCandidate(artifact,test.predictions.slice(0,200),test.resolutions.slice(0,200),now()),later=validatePropCandidate(artifact,test.predictions,test.resolutions.map((r,i)=>i>=200?{...r,status:r.status==='yes'?'no' as const:'yes' as const}:r),now());expect(later.n).toBe(200);expect(later.validationHash).toBe(initial.validationHash);expect(later.brierDifferenceInterval95).toEqual(initial.brierDifferenceInterval95);
 });
 it('requires improvement over an approved incumbent instead of merely beating the raw model',()=>{
  vi.useFakeTimers();vi.setSystemTime(new Date('2026-06-01T00:00:00Z'));const train=training(),test=holdout(),artifact=fitPropCalibrator(train.predictions,train.resolutions,{category:'receivingYards',modelVersion:'SYNTHETIC-PBP-V6',asOf:'2026-06-01T00:00:00Z'});vi.setSystemTime(now());const initial=validatePropCandidate(artifact,test.predictions,test.resolutions,now()),approved=approvePropCalibrator(artifact,initial);
  // A later candidate with identical calibration cannot be promoted over the
  // incumbent solely because both improve on the old uncalibrated baseline.
  const later=cohort('2026-07-02T12:00:00Z',200,'SYNTHETIC-LATER'),candidate=fitPropCalibrator(train.predictions,train.resolutions,{category:artifact.category,modelVersion:artifact.modelVersion,asOf:'2026-07-01T00:00:00Z'});vi.setSystemTime(new Date('2026-08-01T00:00:00Z'));const validation=validatePropCandidate(candidate,later.predictions,later.resolutions,new Date(),approved);expect(validation.incumbentId).toBe(approved.id);expect(validation.eligibleForPromotion).toBe(false);expect(validation.reasons).toContain('brier_improvement_not_established');expect(validation.brierDifferenceInterval95).toEqual([0,0]);
 });
 it('never trains on retrospective imports, future resolutions or one-class datasets',()=>{
  vi.useFakeTimers();vi.setSystemTime(new Date('2026-06-01T00:00:00Z'));const train=training(),config={category:'receivingYards',modelVersion:'SYNTHETIC-PBP-V6',asOf:'2026-06-01T00:00:00Z'};
  expect(()=>fitPropCalibrator(train.predictions.map(p=>({...p,retrospective:true})),train.resolutions,config)).toThrow(/Insufficient prospective/);expect(()=>fitPropCalibrator(train.predictions,train.resolutions.map(r=>({...r,resolvedAt:'2026-07-01T00:00:00Z'})),config)).toThrow(/Insufficient prospective/);expect(()=>fitPropCalibrator(train.predictions,train.resolutions.map(r=>({...r,status:'yes'})),config)).toThrow(/Insufficient prospective/);
 });
 it('blocks calibration fitting and promotion when unresolved under outcomes would bias a resolved subset',()=>{
  vi.useFakeTimers();vi.setSystemTime(new Date('2026-06-01T00:00:00Z'));const train=training(),test=holdout(),config={category:'receivingYards',modelVersion:'SYNTHETIC-PBP-V6',asOf:'2026-06-01T00:00:00Z'},candidate=fitPropCalibrator(train.predictions,train.resolutions,config);
  // Drop one known No from a large otherwise well-covered cohort. Sample size
  // alone must not allow the selected, upward-biased resolved subset to pass.
  const trainingNo=train.resolutions.find(row=>row.status==='no')!;expect(()=>fitPropCalibrator(train.predictions,train.resolutions.filter(row=>row.id!==trainingNo.id),config)).toThrow(/unresolved mature forecasts/);
  vi.setSystemTime(now());const heldoutNo=test.resolutions.find(row=>row.status==='no')!,validation=validatePropCandidate(candidate,test.predictions,test.resolutions.filter(row=>row.id!==heldoutNo.id),now());expect(validation.n).toBeGreaterThan(100);expect(validation.eligibleForPromotion).toBe(false);expect(validation.reasons).toContain('incomplete_prospective_outcome_coverage');expect(validation.coverage).toMatchObject({unresolvedPredictions:1,promotionBlocked:true});expect(()=>approvePropCalibrator(candidate,validation)).toThrow(/remains unapproved/);
 });
 it('excludes recent resolved subsets from training until their complete outcome coverage matures',()=>{
  vi.useFakeTimers();vi.setSystemTime(new Date('2026-06-01T12:00:00Z'));const train=training(),recent=cohort('2026-06-01T07:00:00Z',1,'SYNTHETIC-RECENT-TRAIN'),config={category:'receivingYards',modelVersion:'SYNTHETIC-PBP-V6',asOf:'2026-06-01T12:00:00Z'},missing=recent.resolutions[0];
  const predictions=[...train.predictions,...recent.predictions],partial=[...train.resolutions,...recent.resolutions.filter(row=>row.id!==missing.id)],baseline=fitPropCalibrator(train.predictions,train.resolutions,config),early=fitPropCalibrator(predictions,partial,config);
  expect(early.trainingHash).toBe(baseline.trainingHash);expect(early.trainingSampleSize).toBe(baseline.trainingSampleSize);
  vi.setSystemTime(new Date('2026-06-01T13:00:00Z'));const mature={...config,asOf:'2026-06-01T13:00:00Z'};expect(()=>fitPropCalibrator(predictions,partial,mature)).toThrow(/unresolved mature forecasts/);
  expect(fitPropCalibrator(predictions,[...partial,missing],mature).trainingSampleSize).toBe(baseline.trainingSampleSize+5);
 });
 it('keeps a partially resolved recent game out of the frozen holdout until mature and complete',()=>{
  vi.useFakeTimers();vi.setSystemTime(new Date('2026-06-01T00:00:00Z'));const train=training(),test=cohort('2026-06-02T12:00:00Z',40,'SYNTHETIC-MATURING-HOLDOUT'),candidate=fitPropCalibrator(train.predictions,train.resolutions,{category:'receivingYards',modelVersion:'SYNTHETIC-PBP-V6',asOf:'2026-06-01T00:00:00Z'}),lastGame=test.predictions.at(-1)!.gameId,missing=test.resolutions.find(row=>row.status==='no'&&test.predictions.find(prediction=>prediction.id===row.predictionId)!.gameId===lastGame)!,partial=test.resolutions.filter(row=>row.id!==missing.id),eventAt=Date.parse(test.predictions.at(-1)!.eventStart);
  vi.setSystemTime(new Date(eventAt+5*3600000));const early=validatePropCandidate(candidate,test.predictions,partial,new Date());expect(early.n).toBe(195);expect(early.games).toBe(39);expect(early.reasons).toContain('frozen_future_game_holdout_incomplete');expect(early.eligibleForPromotion).toBe(false);
  vi.setSystemTime(new Date(eventAt+6*3600000));const mature=validatePropCandidate(candidate,test.predictions,partial,new Date());expect(mature.reasons).toContain('incomplete_prospective_outcome_coverage');expect(mature.eligibleForPromotion).toBe(false);
  const complete=validatePropCandidate(candidate,test.predictions,test.resolutions,new Date());expect(complete.n).toBe(200);expect(complete.games).toBe(40);expect(complete.eligibleForPromotion).toBe(true);
 });
 it('flags probability/model drift for review without retraining or automatic promotion',()=>{
  expect(propModelDrift([])).toMatchObject({status:'insufficient_evidence',automaticRetraining:false});const train=training(),scored=scorePropObservations(train.predictions,train.resolutions,now()).rows;expect(propModelDrift(scored)).toMatchObject({status:'evaluated',automaticRetraining:false});const mixed=[...scored,{...scored[0],category:'rushingYards'}];expect(propModelDrift(mixed).status).toBe('not_comparable');
 });
});
