/** Server-side prospective prop auditing and controlled calibration.
 *
 * No probabilities, historical results, or approved artifacts are supplied here.
 * A new calibrator starts as a candidate and must survive a subsequent, game-
 * blocked holdout before it can be used. Retrospective imports never qualify.
 */
import {createHash} from 'node:crypto';

export const PROP_EVALUATION_PROTOCOL='prop-prospective-game-block-6.0.0';
const PROP_OUTCOME_MATURATION_MS=6*3600000;
export type PropOperator='gt'|'gte'|'lt'|'lte'|'eq';
export type PropBinaryOutcome='yes'|'no'|'void'|'unresolved';
export type FrozenPropPrediction={
 id:string;contractId:string;gameId:string;playerId:string;category:string;
 threshold:number;operator:PropOperator;side?:'YES'|'NO';
 rawProbability:number;calibratedProbability?:number|null;calibrationArtifactId?:string|null;
 marketProbability?:number|null;modelVersion:string;inputVersion:string;rulesHash?:string;
 predictedAt:string;eventStart:string;dataAvailableAt:string;archivedAt?:string;
 retrospective?:boolean;
};
export type VerifiedPropResolution={
 id:string;predictionId:string;status:PropBinaryOutcome;resolvedAt:string;
 sourceUrl:string;sourceVersion:string;verifiedFinal:boolean;availableAt?:string;
 previousResolutionId?:string|null;rulesHash?:string;observedValue?:number|null;
};
export type PropStatContract={
 gameId:string;playerId:string;category:string;threshold:number;operator:PropOperator;
 rulesVerified:boolean;dnpRule:'void'|'settle_zero'|'unverified';
 includesOvertime:boolean;fullGame:boolean;rulesHash?:string;
};
export type FinalPlayerStatistic={
 gameId:string;playerId:string;category:string;value:number|null;
 gameFinal:boolean;fullGame:boolean;includesOvertime:boolean;participated:boolean|null;
 checkedAt:string;sourceUrl:string;sourceVersion:string;verified:boolean;
 providerVoided?:boolean;exceptionalSettlementUnresolved?:boolean;
};
export type ScoredPropObservation={
 predictionId:string;contractId:string;gameId:string;playerId:string;category:string;
 modelVersion:string;rawProbability:number;calibratedProbability:number|null;
 marketProbability:number|null;outcome:0|1;predictedAt:string;eventStart:string;
 resolvedAt:string;availableAt:string;sourceUrl:string;sourceVersion:string;
};
type MetricRow={gameId:string;p:number;y:number};
export type PropMetric={
 n:number;games:number;contracts?:number;brier:number;logLoss:number;
 predictedRate:number;observedRate:number;classificationAccuracy:number;
 brierInterval95:[number,number]|null;expectedCalibrationError:number;
 calibration:Array<{from:number;to:number;n:number;games:number;predicted:number|null;observed:number|null;observedInterval95:[number,number]|null}>;
};
type Exclusion={predictionId:string;reason:string};
const probability=(value:unknown):value is number=>typeof value==='number'&&Number.isFinite(value)&&value>=0&&value<=1;
const text=(value:unknown):value is string=>typeof value==='string'&&value.trim().length>0;
const time=(value:unknown)=>typeof value==='string'&&/(?:Z|[+-]\d{2}:\d{2})$/.test(value)&&Number.isFinite(Date.parse(value))?Date.parse(value):NaN;
const sourceUrl=(value:unknown)=>{try{return typeof value==='string'&&new URL(value).protocol==='https:';}catch{return false;}};
const mean=(values:number[])=>values.reduce((sum,value)=>sum+value,0)/values.length;
const clamp=(p:number,epsilon=1e-12)=>Math.min(1-epsilon,Math.max(epsilon,p));
const logLoss=(p:number,y:number)=>-y*Math.log(clamp(p))-(1-y)*Math.log(1-clamp(p));
const hash=(value:unknown)=>createHash('sha256').update(JSON.stringify(value)).digest('hex');

/** Compare the exact contract definition, never a rounded chart bin. */
export function comparePropThreshold(value:number,threshold:number,operator:PropOperator):boolean{
 if(!Number.isFinite(value)||!Number.isFinite(threshold))throw new Error('A finite observed statistic and exact threshold are required.');
 switch(operator){case'gt':return value>threshold;case'gte':return value>=threshold;case'lt':return value<threshold;case'lte':return value<=threshold;case'eq':return value===threshold;default:throw new Error('Unsupported exact-threshold operator.');}
}

/** Research outcome only. This never settles a personal wager or assumes an
 * exchange's exceptional settlement from a final box score alone. */
export function resolvePropOutcome(contract:PropStatContract,stat:FinalPlayerStatistic){
 const unresolved=(reason:string)=>({status:'unresolved' as PropBinaryOutcome,observedValue:null as number|null,reason,exchangeSettlementVerified:false,sourceUrl:stat.sourceUrl,sourceVersion:stat.sourceVersion,checkedAt:stat.checkedAt});
 if(!contract.rulesVerified||!contract.fullGame||!['gt','gte','lt','lte','eq'].includes(contract.operator)||!Number.isFinite(contract.threshold))return unresolved('Exact full-game contract settlement rules have not been verified.');
 if(contract.gameId!==stat.gameId||contract.playerId!==stat.playerId||contract.category!==stat.category)return unresolved('The final statistic does not match the exact game, player and statistic.');
 if(!stat.verified||!sourceUrl(stat.sourceUrl)||!text(stat.sourceVersion)||!Number.isFinite(time(stat.checkedAt)))return unresolved('Verified final-statistic provenance and its timestamp are required.');
 if(stat.providerVoided===true)return{...unresolved('The provider explicitly voided this contract.'),status:'void' as PropBinaryOutcome,exchangeSettlementVerified:true};
 if(stat.exceptionalSettlementUnresolved)return unresolved('An exceptional settlement condition remains unresolved; a binary outcome is withheld.');
 if(!stat.gameFinal||!stat.fullGame||contract.includesOvertime!==stat.includesOvertime)return unresolved('A final statistic with matching full-game/overtime coverage is required.');
 if(stat.participated===false&&contract.dnpRule==='void')return{...unresolved('The verified non-participation rule voids this contract.'),status:'void' as PropBinaryOutcome};
 if(stat.participated===null&&contract.dnpRule!=='settle_zero')return unresolved('Player participation is not verified for this contract\'s non-participation rule.');
 if(stat.participated===false&&contract.dnpRule==='unverified')return unresolved('The non-participation settlement rule is unavailable.');
 const value=stat.participated===false&&contract.dnpRule==='settle_zero'?0:stat.value;
 if(typeof value!=='number'||!Number.isFinite(value))return unresolved('The exact final player statistic is unavailable; a missing value is not zero.');
 return{status:(comparePropThreshold(value,contract.threshold,contract.operator)?'yes':'no') as PropBinaryOutcome,observedValue:value,reason:'Exact verified full-game statistic compared with the frozen contract threshold. This is a research resolution, not confirmation of an exchange payout.',exchangeSettlementVerified:false,sourceUrl:stat.sourceUrl,sourceVersion:stat.sourceVersion,checkedAt:stat.checkedAt};
}

export function auditPropPrediction(prediction:FrozenPropPrediction,now=new Date()):string[]{
 const reasons:string[]=[];
 for(const key of ['id','contractId','gameId','playerId','category','modelVersion','inputVersion'] as const)if(!text(prediction[key]))reasons.push('missing_'+key);
 if(!Number.isFinite(prediction.threshold)||!['gt','gte','lt','lte','eq'].includes(prediction.operator))reasons.push('invalid_threshold_definition');
 if(!probability(prediction.rawProbability))reasons.push('invalid_probability');
 if(prediction.side!==undefined&&!['YES','NO'].includes(prediction.side))reasons.push('invalid_side');
 const predicted=time(prediction.predictedAt),event=time(prediction.eventStart),available=time(prediction.dataAvailableAt),archived=time(prediction.archivedAt??prediction.predictedAt);
 if(![predicted,event,available,archived].every(Number.isFinite))reasons.push('missing_timezone_aware_timestamps');
 else{
  if(predicted>=event||archived>=event)reasons.push('not_archived_before_kickoff');
  if(available>predicted)reasons.push('look_ahead_inputs');
  if(archived<predicted)reasons.push('archive_precedes_prediction');
  if(predicted>now.getTime()+60000||archived>now.getTime()+60000)reasons.push('future_prediction_timestamp');
 }
 if(prediction.retrospective)reasons.push('retrospective_import');
 return reasons;
}

function resolutionsByPrediction(resolutions:VerifiedPropResolution[]){
 const groups=new Map<string,VerifiedPropResolution[]>();
 for(const resolution of resolutions){const group=groups.get(resolution.predictionId)??[];group.push(resolution);groups.set(resolution.predictionId,group);}
 const result=new Map<string,{resolution:VerifiedPropResolution|null;reason?:string}>();
 for(const[id,group]of groups){
  group.sort((a,b)=>time(a.resolvedAt)-time(b.resolvedAt)||a.id.localeCompare(b.id));
  let previous:VerifiedPropResolution|null=null,reason:string|undefined;
  const seen=new Set<string>();
  for(const current of group){
   if(!text(current.id)||seen.has(current.id)){reason='duplicate_resolution_identity';break;}seen.add(current.id);
   if(previous){if(current.previousResolutionId!==previous.id||time(current.resolvedAt)<=time(previous.resolvedAt)){reason='ambiguous_resolution_correction';break;}}
   else if(current.previousResolutionId){reason='missing_original_resolution';break;}
   previous=current;
  }
  result.set(id,{resolution:reason?null:previous,reason});
 }
 return result;
}

/** Deterministic protocol: latest pre-kickoff snapshot for each exact contract
 * and model version, selected without looking at its outcome. YES/NO snapshots
 * are represented once in the canonical YES target, not double-counted. */
export function scorePropObservations(predictions:FrozenPropPrediction[],resolutions:VerifiedPropResolution[],now=new Date()){
 if(predictions.length>200000||resolutions.length>400000)throw new Error('Partition very large evaluation histories explicitly.');
 const exclusions:Exclusion[]=[],selected=new Map<string,FrozenPropPrediction>(),ids=new Map<string,number>();
 for(const prediction of predictions)ids.set(prediction.id,(ids.get(prediction.id)??0)+1);
 for(const prediction of predictions){
  const reasons=auditPropPrediction(prediction,now);
  if((ids.get(prediction.id)??0)>1)reasons.push('duplicate_prediction_identity');
  if(reasons.length){for(const reason of reasons)exclusions.push({predictionId:prediction.id,reason});continue;}
  const key=JSON.stringify([prediction.modelVersion,prediction.contractId,prediction.gameId,prediction.playerId,prediction.category,prediction.threshold,prediction.operator,prediction.rulesHash??'']);
  const old=selected.get(key);
  if(!old||time(prediction.predictedAt)>time(old.predictedAt)||time(prediction.predictedAt)===time(old.predictedAt)&&(prediction.side!=='NO'&&old.side==='NO'||prediction.side===old.side&&prediction.id.localeCompare(old.id)>0)){
   if(old)exclusions.push({predictionId:old.id,reason:'earlier_snapshot_same_contract_model'});selected.set(key,prediction);
  }else exclusions.push({predictionId:prediction.id,reason:'earlier_snapshot_same_contract_model'});
 }
 const resolved=resolutionsByPrediction(resolutions),rows:ScoredPropObservation[]=[];
 for(const prediction of selected.values()){
  const entry=resolved.get(prediction.id),resolution=entry?.resolution;
  const exclude=(reason:string)=>exclusions.push({predictionId:prediction.id,reason});
  if(!resolution){exclude(entry?.reason??'unresolved');continue;}
  if(!resolution.verifiedFinal||!sourceUrl(resolution.sourceUrl)||!text(resolution.sourceVersion)){exclude('unverified_final_source');continue;}
  const resolvedAt=time(resolution.resolvedAt),available=time(resolution.availableAt??resolution.resolvedAt);
  if(!Number.isFinite(resolvedAt)||!Number.isFinite(available)||resolvedAt<time(prediction.eventStart)||available<time(prediction.eventStart)||available>resolvedAt||resolvedAt>now.getTime()+60000){exclude('invalid_resolution_time');continue;}
  if(prediction.rulesHash&&resolution.rulesHash!==prediction.rulesHash){exclude('settlement_rules_changed_or_missing');continue;}
  if(resolution.status==='void'){exclude('void_not_binary');continue;}
  if(!['yes','no'].includes(resolution.status)){exclude('unresolved');continue;}
  const canonical=(p:number)=>prediction.side==='NO'?1-p:p;
  rows.push({predictionId:prediction.id,contractId:prediction.contractId,gameId:prediction.gameId,playerId:prediction.playerId,category:prediction.category,modelVersion:prediction.modelVersion,
   rawProbability:canonical(prediction.rawProbability),calibratedProbability:probability(prediction.calibratedProbability)&&text(prediction.calibrationArtifactId)?canonical(prediction.calibratedProbability):null,
   marketProbability:probability(prediction.marketProbability)?canonical(prediction.marketProbability):null,outcome:resolution.status==='yes'?1:0,
   predictedAt:new Date(time(prediction.predictedAt)).toISOString(),eventStart:new Date(time(prediction.eventStart)).toISOString(),resolvedAt:new Date(resolvedAt).toISOString(),availableAt:new Date(available).toISOString(),sourceUrl:resolution.sourceUrl,sourceVersion:resolution.sourceVersion});
 }
 rows.sort((a,b)=>time(a.eventStart)-time(b.eventStart)||a.predictionId.localeCompare(b.predictionId));
 return{rows,exclusions,protocol:PROP_EVALUATION_PROTOCOL,selection:'Latest eligible snapshot per exact contract and model version; canonical YES target; no outcome-dependent selection.'};
}

/** A resolved subset can be systematically biased, especially when zero-touch
 * participants have missing final statistics. Promotion therefore fails closed
 * until every selected mature forecast in its scope has a verified binary or
 * void resolution. Missing rows are never interpreted as zero or inactivity. */
export function propOutcomeCoverage(predictions:FrozenPropPrediction[],resolutions:VerifiedPropResolution[],now=new Date(),scope?:{category:string;modelVersion:string}){
 const scored=scorePropObservations(predictions,resolutions,now),excluded=new Set(scored.exclusions.filter(row=>['earlier_snapshot_same_contract_model','duplicate_prediction_identity'].includes(row.reason)).map(row=>row.predictionId));
 const selected=predictions.filter(row=>(!scope||row.category===scope.category&&row.modelVersion===scope.modelVersion)&&auditPropPrediction(row,now).length===0&&!excluded.has(row.id)&&time(row.eventStart)<=now.getTime()-PROP_OUTCOME_MATURATION_MS),resolved=resolutionsByPrediction(resolutions);
 const missing:Exclusion[]=[],games=new Set<string>();let complete=0;
 for(const prediction of selected){games.add(prediction.gameId);const resolution=resolved.get(prediction.id)?.resolution;
  const known=resolution&&resolution.verifiedFinal&&['yes','no','void'].includes(resolution.status)&&sourceUrl(resolution.sourceUrl)&&text(resolution.sourceVersion)&&Number.isFinite(time(resolution.resolvedAt))&&time(resolution.resolvedAt)<=now.getTime()+60000&&(!prediction.rulesHash||prediction.rulesHash===resolution.rulesHash);
  if(known)complete++;else missing.push({predictionId:prediction.id,reason:'missing_verified_complete_outcome'});
 }
 return{selectedMaturePredictions:selected.length,verifiedCompletePredictions:complete,unresolvedPredictions:missing.length,games:games.size,promotionBlocked:missing.length>0,policy:'Every latest eligible forecast older than six hours needs a verified binary or void outcome. Unresolved cases block calibration; six hours is a maturation grace period, not proof a game finished.',unresolved:missing};
}

function rng(seed:number){let state=(seed>>>0)||2026;return()=>{state^=state<<13;state^=state>>>17;state^=state<<5;return(state>>>0)/4294967296;};}
function quantile(values:number[],p:number){const at=(values.length-1)*p,low=Math.floor(at),high=Math.ceil(at);return values[low]+(values[high]-values[low])*(at-low);}
/** Game-block bootstrap, preserving all correlated props within each game. */
export function gameBlockInterval(values:Array<{gameId:string;value:number}>,seed=2026,repeats=1000):[number,number]|null{
 const blocks=new Map<string,{sum:number;n:number}>();
 for(const row of values){if(!Number.isFinite(row.value))throw new Error('Bootstrap values must be finite.');const block=blocks.get(row.gameId)??{sum:0,n:0};block.sum+=row.value;block.n++;blocks.set(row.gameId,block);}
 if(blocks.size<8)return null;
 if(!Number.isSafeInteger(repeats)||repeats<100||repeats>5000)throw new Error('Use100–5,000 reproducible bootstrap repeats.');
 const groups=[...blocks.values()],random=rng(seed),samples:number[]=[];
 for(let i=0;i<repeats;i++){let total=0,n=0;for(let j=0;j<groups.length;j++){const block=groups[Math.floor(random()*groups.length)];total+=block.sum;n+=block.n;}samples.push(total/n);}
 samples.sort((a,b)=>a-b);return[quantile(samples,.025),quantile(samples,.975)];
}

export function propProbabilityMetrics(rows:MetricRow[]):PropMetric|null{
 if(!rows.length)return null;
 if(rows.some(r=>!probability(r.p)||r.y!==0&&r.y!==1||!text(r.gameId)))throw new Error('Metrics require actual binary outcomes and finite probabilities.');
 const calibration=Array.from({length:10},(_,bucket)=>{
  const group=rows.filter(row=>Math.min(9,Math.floor(row.p*10))===bucket);
  return{from:bucket/10,to:(bucket+1)/10,n:group.length,games:new Set(group.map(row=>row.gameId)).size,predicted:group.length?mean(group.map(row=>row.p)):null,observed:group.length?mean(group.map(row=>row.y)):null,observedInterval95:group.length?gameBlockInterval(group.map(row=>({gameId:row.gameId,value:row.y})),2026+bucket):null};
 });
 return{n:rows.length,games:new Set(rows.map(row=>row.gameId)).size,brier:mean(rows.map(row=>(row.p-row.y)**2)),logLoss:mean(rows.map(row=>logLoss(row.p,row.y))),predictedRate:mean(rows.map(row=>row.p)),observedRate:mean(rows.map(row=>row.y)),classificationAccuracy:mean(rows.map(row=>Number((row.p>=.5)===Boolean(row.y)))),brierInterval95:gameBlockInterval(rows.map(row=>({gameId:row.gameId,value:(row.p-row.y)**2}))),expectedCalibrationError:calibration.reduce((sum,bucket)=>sum+bucket.n/rows.length*Math.abs((bucket.predicted??0)-(bucket.observed??0)),0),calibration};
}
function rowMetrics(rows:ScoredPropObservation[]){
 const make=(field:'rawProbability'|'calibratedProbability'|'marketProbability',subset=rows)=>propProbabilityMetrics(subset.filter(row=>probability(row[field])).map(row=>({gameId:row.gameId,p:row[field]!,y:row.outcome})));
 const common=rows.filter(row=>probability(row.marketProbability));
 return{n:rows.length,contracts:new Set(rows.map(row=>row.contractId)).size,games:new Set(rows.map(row=>row.gameId)).size,raw:make('rawProbability'),calibrated:make('calibratedProbability'),market:make('marketProbability'),marketComparison:{commonSampleSize:common.length,rawOnCommon:make('rawProbability',common),calibratedOnCommon:make('calibratedProbability',common),marketOnCommon:make('marketProbability',common)}};
}
function groupRows(rows:ScoredPropObservation[],key:(row:ScoredPropObservation)=>string){const groups=new Map<string,ScoredPropObservation[]>();for(const row of rows){const value=key(row),group=groups.get(value)??[];group.push(row);groups.set(value,group);}return Object.fromEntries([...groups].map(([name,group])=>[name,rowMetrics(group)]));}
export function evaluatePropHistory(predictions:FrozenPropPrediction[],resolutions:VerifiedPropResolution[],now=new Date()){
 const scored=scorePropObservations(predictions,resolutions,now),rows=scored.rows;
 const {unresolved,...coverage}=propOutcomeCoverage(predictions,resolutions,now);
 return{protocol:scored.protocol,selection:scored.selection,asOf:now.toISOString(),totalSnapshots:predictions.length,eligibleResolved:rows.length,exclusions:scored.exclusions,excludedCounts:Object.fromEntries([...new Set(scored.exclusions.map(row=>row.reason))].map(reason=>[reason,scored.exclusions.filter(row=>row.reason===reason).length])),coverage,overall:rowMetrics(rows),byCategory:groupRows(rows,row=>row.category),byModelVersion:groupRows(rows,row=>row.modelVersion),byDate:groupRows(rows,row=>new Date(row.eventStart).toISOString().slice(0,10)),windows:{days7:rowMetrics(rows.filter(row=>time(row.eventStart)>=now.getTime()-7*86400000)),days30:rowMetrics(rows.filter(row=>time(row.eventStart)>=now.getTime()-30*86400000)),allTime:rowMetrics(rows)},rows,
  limitations:['Game-block intervals account for within-game dependence, not source errors, model misspecification or every selection bias.','Only verified prospective binary outcomes enter accuracy/calibration metrics. Voids and retrospective imports remain separately counted.','Market comparisons use the same eligible contracts; unavailable prices are not inferred.']};
}

type IsotonicBlock={upper:number;n:number;successes:number;probability:number};
export type PropCalibrator={
 id:string;protocol:string;category:string;modelVersion:string;method:'isotonic'|'platt';status:'candidate'|'approved';
 createdAt:string;dataCutoff:string;trainingStart:string;trainingThrough:string;
 trainingSampleSize:number;trainingGames:number;trainingHash:string;trainingSnapshotIds:string[];
 validationGameTarget:number;
 minimumRawProbability:number;maximumRawProbability:number;epsilon:number;
 blocks?:IsotonicBlock[];slope?:number;intercept?:number;
 validation?:{id:string;validatedAt:string;sampleSize:number;games:number;firstPredictionAt:string;lastEventAt:string;validationHash:string;brierDifferenceInterval95:[number,number];logLossDifferenceInterval95:[number,number];incumbentId?:string|null;coverageComplete:boolean};
};
export const PROP_CALIBRATION_MINIMUMS={trainingPredictions:200,trainingGames:40,trainingEachOutcome:30,validationPredictions:100,validationGames:20,validationEachOutcome:20} as const;

function fittingRows(predictions:FrozenPropPrediction[],resolutions:VerifiedPropResolution[],options:{category:string;modelVersion:string;asOf:string}){
 const cutoff=time(options.asOf);if(!Number.isFinite(cutoff)||cutoff>Date.now()+60000)throw new Error('A nonfuture, timezone-aware calibration cutoff is required.');
 return scorePropObservations(predictions,resolutions,new Date(cutoff)).rows.filter(row=>row.category===options.category&&row.modelVersion===options.modelVersion&&time(row.eventStart)<=cutoff-PROP_OUTCOME_MATURATION_MS&&time(row.availableAt)<=cutoff);
}
function isotonicFit(rows:ScoredPropObservation[]):IsotonicBlock[]{
 const groups=new Map<number,{n:number;successes:number}>();
 for(const row of rows){const group=groups.get(row.rawProbability)??{n:0,successes:0};group.n++;group.successes+=row.outcome;groups.set(row.rawProbability,group);}
 const blocks:IsotonicBlock[]=[];
 for(const[p,group]of[...groups].sort((a,b)=>a[0]-b[0])){
  blocks.push({upper:p,...group,probability:group.successes/group.n});
  while(blocks.length>=2&&blocks[blocks.length-2].probability>blocks[blocks.length-1].probability){const right=blocks.pop()!,left=blocks.pop()!,n=left.n+right.n,successes=left.successes+right.successes;blocks.push({upper:right.upper,n,successes,probability:successes/n});}
 }
 return blocks;
}
function plattFit(rows:ScoredPropObservation[]){
 const logits=rows.map(row=>Math.log(clamp(row.rawProbability,1e-6)/(1-clamp(row.rawProbability,1e-6))));
 let slope=1,intercept=0,converged=false;
 // A fixed weak L2 penalty regularizes finite-sample separability; no holdout
 // values are used to choose it or the number of iterations.
 for(let iteration=0;iteration<100;iteration++){
  let g0=.001*intercept,g1=.001*slope,h00=.001,h01=0,h11=.001;
  rows.forEach((row,index)=>{const x=logits[index],p=1/(1+Math.exp(-Math.max(-35,Math.min(35,intercept+slope*x)))),w=p*(1-p);g0+=p-row.outcome;g1+=(p-row.outcome)*x;h00+=w;h01+=w*x;h11+=w*x*x;});
  const determinant=h00*h11-h01*h01;if(!Number.isFinite(determinant)||determinant<=1e-12)throw new Error('Calibration fit is numerically unstable.');
  const d0=(h11*g0-h01*g1)/determinant,d1=(h00*g1-h01*g0)/determinant,scale=Math.min(1,2/Math.max(Math.abs(d0),Math.abs(d1),1));
  intercept-=scale*d0;slope-=scale*d1;
  if(!Number.isFinite(intercept)||!Number.isFinite(slope)||Math.abs(slope)>50||Math.abs(intercept)>50)throw new Error('Calibration fit is unstable; no candidate was supplied.');
  if(Math.max(Math.abs(d0),Math.abs(d1))<1e-8){converged=true;break;}
 }
 if(!converged)throw new Error('Calibration optimizer did not converge; candidate withheld.');
 if(slope<=0)throw new Error('A non-monotone Platt fit is not eligible as a calibration candidate.');
 return{slope,intercept};
}
export function fitPropCalibrator(predictions:FrozenPropPrediction[],resolutions:VerifiedPropResolution[],options:{category:string;modelVersion:string;asOf:string;method?:'isotonic'|'platt'}):PropCalibrator{
 if(propOutcomeCoverage(predictions,resolutions,new Date(options.asOf),options).promotionBlocked)throw new Error('Insufficient prospective evidence: unresolved mature forecasts could bias calibration selection. Complete outcome coverage is required.');
 const rows=fittingRows(predictions,resolutions,options),games=new Set(rows.map(row=>row.gameId)),yes=rows.filter(row=>row.outcome===1).length,min=PROP_CALIBRATION_MINIMUMS;
 if(rows.length<min.trainingPredictions||games.size<min.trainingGames||Math.min(yes,rows.length-yes)<min.trainingEachOutcome||new Set(rows.map(row=>row.rawProbability)).size<5)throw new Error('Insufficient prospective evidence for a prop calibrator: require200 predictions,40 games,30 outcomes of each class and probability-range coverage.');
 const method=options.method??'isotonic';if(!['isotonic','platt'].includes(method))throw new Error('Choose a predeclared isotonic or Platt calibration method.');
 const trainingSnapshotIds=rows.map(row=>row.predictionId).sort(),trainingHash=hash(rows.map(row=>[row.predictionId,row.rawProbability,row.outcome,row.sourceVersion]));
 const body={protocol:PROP_EVALUATION_PROTOCOL,category:options.category,modelVersion:options.modelVersion,method,status:'candidate' as const,createdAt:new Date().toISOString(),dataCutoff:options.asOf,trainingStart:rows[0].eventStart,trainingThrough:rows[rows.length-1].eventStart,trainingSampleSize:rows.length,trainingGames:games.size,trainingHash,trainingSnapshotIds,validationGameTarget:40,minimumRawProbability:Math.min(...rows.map(row=>row.rawProbability)),maximumRawProbability:Math.max(...rows.map(row=>row.rawProbability)),epsilon:.5/(rows.length+1),...(method==='isotonic'?{blocks:isotonicFit(rows)}:plattFit(rows))};
 return{...body,id:'prop-cal-'+hash(body)};
}
function candidateProbability(raw:number,artifact:PropCalibrator):number|null{
 if(!probability(raw)||raw<artifact.minimumRawProbability||raw>artifact.maximumRawProbability)return null;
 let value:number;
 if(artifact.method==='isotonic'){
  const blocks=artifact.blocks;if(!blocks?.length)return null;const block=blocks.find(block=>raw<=block.upper)??blocks[blocks.length-1];value=block.probability;
 }else if(artifact.method==='platt'&&Number.isFinite(artifact.slope)&&Number.isFinite(artifact.intercept))value=1/(1+Math.exp(-(artifact.intercept!+artifact.slope!*Math.log(clamp(raw,1e-6)/(1-clamp(raw,1e-6))))));
 else return null;
 return probability(value)?clamp(value,artifact.epsilon):null;
}
export type PropCandidateValidation={
 id:string;protocol:string;candidateId:string;category:string;modelVersion:string;validatedAt:string;
 eligibleForPromotion:boolean;reasons:string[];n:number;games:number;raw:PropMetric|null;candidate:PropMetric|null;
 brierDifferenceInterval95:[number,number]|null;logLossDifferenceInterval95:[number,number]|null;
 firstPredictionAt:string|null;lastEventAt:string|null;validationHash:string;
 incumbentId:string|null;comparisonBaseline:PropMetric|null;
 coverage:{selectedMaturePredictions:number;verifiedCompletePredictions:number;unresolvedPredictions:number;games:number;promotionBlocked:boolean;policy:string};
 marketAdvantageEstablished:boolean;marketComparison:{n:number;candidate:PropMetric|null;market:PropMetric|null;brierDifferenceInterval95:[number,number]|null};
};
export function validatePropCandidate(candidate:PropCalibrator,predictions:FrozenPropPrediction[],resolutions:VerifiedPropResolution[],now=new Date(),incumbent:PropCalibrator|null=null):PropCandidateValidation{
 const reasons:string[]=[],all=scorePropObservations(predictions,resolutions,now).rows;
 const {unresolved,...coverage}=propOutcomeCoverage(predictions,resolutions,now,{category:candidate.category,modelVersion:candidate.modelVersion});
 if(coverage.promotionBlocked)reasons.push('incomplete_prospective_outcome_coverage');
 if(!validArtifact(candidate))throw new Error('The calibration artifact is malformed or lacks a frozen holdout protocol.');
 const future=all.filter(row=>row.category===candidate.category&&row.modelVersion===candidate.modelVersion&&time(row.predictedAt)>time(candidate.createdAt)&&time(row.eventStart)>time(candidate.dataCutoff)&&time(row.eventStart)<=now.getTime()-PROP_OUTCOME_MATURATION_MS&&!candidate.trainingSnapshotIds.includes(row.predictionId));
 // The same first40 future game blocks remain the holdout forever. Continual
 // peeking cannot add favorable later games to rescue a rejected candidate.
 const firstGames=new Set([...new Set(future.map(row=>row.gameId))].slice(0,candidate.validationGameTarget)),rows=future.filter(row=>firstGames.has(row.gameId));
 const baseline=(row:ScoredPropObservation)=>incumbent?applyPropCalibration(row.rawProbability,incumbent,{category:row.category,modelVersion:row.modelVersion,predictedAt:row.predictedAt}):row.rawProbability;
 const covered=rows.filter(row=>candidateProbability(row.rawProbability,candidate)!==null&&baseline(row)!==null),games=new Set(covered.map(row=>row.gameId)),yes=covered.filter(row=>row.outcome===1).length,min=PROP_CALIBRATION_MINIMUMS;
 if(firstGames.size<candidate.validationGameTarget)reasons.push('frozen_future_game_holdout_incomplete');
 if(incumbent&&(incumbent.category!==candidate.category||incumbent.modelVersion!==candidate.modelVersion))reasons.push('incumbent_scope_mismatch');
 if(candidate.protocol!==PROP_EVALUATION_PROTOCOL)reasons.push('unsupported_protocol');
 if(!Number.isFinite(time(candidate.createdAt))||time(candidate.dataCutoff)>time(candidate.createdAt)+60000)reasons.push('invalid_candidate_chronology');
 if(covered.length<min.validationPredictions||games.size<min.validationGames||Math.min(yes,covered.length-yes)<min.validationEachOutcome)reasons.push('insufficient_subsequent_prospective_holdout');
 if(rows.length&&covered.length<rows.length*.9)reasons.push('insufficient_holdout_probability_range_coverage');
 const raw=propProbabilityMetrics(covered.map(row=>({gameId:row.gameId,p:row.rawProbability,y:row.outcome}))),calibrated=propProbabilityMetrics(covered.map(row=>({gameId:row.gameId,p:candidateProbability(row.rawProbability,candidate)!,y:row.outcome})));
 const comparisonBaseline=propProbabilityMetrics(covered.map(row=>({gameId:row.gameId,p:baseline(row)!,y:row.outcome})));
 const brier=gameBlockInterval(covered.map(row=>({gameId:row.gameId,value:(candidateProbability(row.rawProbability,candidate)!-row.outcome)**2-(baseline(row)!-row.outcome)**2}))),loss=gameBlockInterval(covered.map(row=>({gameId:row.gameId,value:logLoss(candidateProbability(row.rawProbability,candidate)!,row.outcome)-logLoss(baseline(row)!,row.outcome)})),2027);
 if(!brier||brier[1]>=0)reasons.push('brier_improvement_not_established');
 if(!loss||loss[1]>=0)reasons.push('log_loss_improvement_not_established');
 if(comparisonBaseline&&calibrated&&calibrated.expectedCalibrationError>comparisonBaseline.expectedCalibrationError)reasons.push('calibration_error_regressed');
 if(covered.length>=min.validationPredictions){
  // Both chronological halves must improve in point Brier; one lucky cluster
  // must not be the entire evidence for a promotion.
  const dates=[...new Set(covered.map(row=>row.eventStart))].sort(),middle=dates[Math.floor(dates.length/2)];
  for(const half of [covered.filter(row=>row.eventStart<middle),covered.filter(row=>row.eventStart>=middle)])if(!half.length||mean(half.map(row=>(candidateProbability(row.rawProbability,candidate)!-row.outcome)**2-(baseline(row)!-row.outcome)**2))>=0)reasons.push('temporal_stability_not_established');
 }
 const common=covered.filter(row=>probability(row.marketProbability)),marketDifference=gameBlockInterval(common.map(row=>({gameId:row.gameId,value:(candidateProbability(row.rawProbability,candidate)!-row.outcome)**2-(row.marketProbability!-row.outcome)**2})),2028);
 const body={protocol:PROP_EVALUATION_PROTOCOL,candidateId:candidate.id,category:candidate.category,modelVersion:candidate.modelVersion,validatedAt:now.toISOString(),eligibleForPromotion:reasons.length===0,reasons:[...new Set(reasons)],n:covered.length,games:games.size,raw,candidate:calibrated,brierDifferenceInterval95:brier,logLossDifferenceInterval95:loss,firstPredictionAt:covered.length?covered.reduce((at,row)=>time(row.predictedAt)<time(at)?row.predictedAt:at,covered[0].predictedAt):null,lastEventAt:covered.length?covered[covered.length-1].eventStart:null,validationHash:hash(covered.map(row=>[row.predictionId,row.rawProbability,row.outcome,row.sourceVersion])),incumbentId:incumbent?.id??null,comparisonBaseline,coverage,marketAdvantageEstablished:common.length>=min.validationPredictions&&Boolean(marketDifference&&marketDifference[1]<0),marketComparison:{n:common.length,candidate:propProbabilityMetrics(common.map(row=>({gameId:row.gameId,p:candidateProbability(row.rawProbability,candidate)!,y:row.outcome}))),market:propProbabilityMetrics(common.map(row=>({gameId:row.gameId,p:row.marketProbability!,y:row.outcome}))),brierDifferenceInterval95:marketDifference}};
 return{...body,id:'prop-validation-'+hash(body)};
}
export function approvePropCalibrator(candidate:PropCalibrator,validation:PropCandidateValidation):PropCalibrator{
 if(!validArtifact(candidate)||!validation.eligibleForPromotion||!validation.coverage||validation.coverage.promotionBlocked||validation.candidateId!==candidate.id||validation.protocol!==candidate.protocol||validation.category!==candidate.category||validation.modelVersion!==candidate.modelVersion||validation.n<PROP_CALIBRATION_MINIMUMS.validationPredictions||validation.games<candidate.validationGameTarget||!validation.firstPredictionAt||time(validation.firstPredictionAt)<=time(candidate.createdAt)||!validation.lastEventAt||!validation.brierDifferenceInterval95||validation.brierDifferenceInterval95[1]>=0||!validation.logLossDifferenceInterval95||validation.logLossDifferenceInterval95[1]>=0)throw new Error('A matching, subsequent prospective validation certificate is required; candidate remains unapproved.');
 return{...candidate,status:'approved',validation:{id:validation.id,validatedAt:validation.validatedAt,sampleSize:validation.n,games:validation.games,firstPredictionAt:validation.firstPredictionAt,lastEventAt:validation.lastEventAt,validationHash:validation.validationHash,brierDifferenceInterval95:validation.brierDifferenceInterval95,logLossDifferenceInterval95:validation.logLossDifferenceInterval95,incumbentId:validation.incumbentId,coverageComplete:true}};
}
function validArtifact(artifact:PropCalibrator){
 if(!artifact||!text(artifact.id)||!Number.isFinite(time(artifact.createdAt))||!Number.isFinite(time(artifact.dataCutoff))||time(artifact.dataCutoff)>time(artifact.createdAt)||artifact.trainingSampleSize<PROP_CALIBRATION_MINIMUMS.trainingPredictions||artifact.trainingGames<PROP_CALIBRATION_MINIMUMS.trainingGames||!Array.isArray(artifact.trainingSnapshotIds)||artifact.trainingSnapshotIds.length!==artifact.trainingSampleSize||artifact.validationGameTarget!==40||!probability(artifact.minimumRawProbability)||!probability(artifact.maximumRawProbability)||artifact.minimumRawProbability>artifact.maximumRawProbability||!Number.isFinite(artifact.epsilon)||artifact.epsilon<=0||artifact.epsilon>=.5)return false;
 if(artifact.method==='platt')return Number.isFinite(artifact.slope)&&artifact.slope!>0&&Number.isFinite(artifact.intercept);
 if(artifact.method!=='isotonic'||!Array.isArray(artifact.blocks)||!artifact.blocks.length)return false;
 let previous=-1,level=-1,total=0;
 for(const block of artifact.blocks){if(!probability(block.upper)||block.upper<previous||!probability(block.probability)||block.probability<level||!Number.isSafeInteger(block.n)||block.n<1||!Number.isSafeInteger(block.successes)||block.successes<0||block.successes>block.n||Math.abs(block.probability-block.successes/block.n)>1e-10)return false;previous=block.upper;level=block.probability;total+=block.n;}
 return total===artifact.trainingSampleSize&&previous===artifact.maximumRawProbability;
}
/** Never silently calibrate a new model/category with an unrelated audit. */
export function applyPropCalibration(raw:number,artifact:PropCalibrator|null|undefined,context:{category:string;modelVersion:string;predictedAt:string}):number|null{
 const checked=time(context.predictedAt),v=artifact?.validation;
 if(!artifact||!validArtifact(artifact)||artifact.status!=='approved'||artifact.protocol!==PROP_EVALUATION_PROTOCOL||artifact.category!==context.category||artifact.modelVersion!==context.modelVersion||!v||v.coverageComplete!==true||!Number.isFinite(checked)||!Number.isFinite(time(v.validatedAt))||!Number.isFinite(time(v.firstPredictionAt))||!Number.isFinite(time(v.lastEventAt))||time(v.validatedAt)>checked||time(v.validatedAt)<time(v.lastEventAt)||time(v.firstPredictionAt)<=time(artifact.createdAt)||v.sampleSize<PROP_CALIBRATION_MINIMUMS.validationPredictions||v.games<artifact.validationGameTarget||!Array.isArray(v.brierDifferenceInterval95)||!Array.isArray(v.logLossDifferenceInterval95)||v.brierDifferenceInterval95.length!==2||v.logLossDifferenceInterval95.length!==2||v.brierDifferenceInterval95.some(p=>!Number.isFinite(p))||v.logLossDifferenceInterval95.some(p=>!Number.isFinite(p))||v.brierDifferenceInterval95[0]>v.brierDifferenceInterval95[1]||v.logLossDifferenceInterval95[0]>v.logLossDifferenceInterval95[1]||v.brierDifferenceInterval95[1]>=0||v.logLossDifferenceInterval95[1]>=0)return null;
 return candidateProbability(raw,artifact);
}

export function propModelDrift(rows:ScoredPropObservation[]){
 const sorted=[...rows].sort((a,b)=>time(a.eventStart)-time(b.eventStart));
 if(new Set(rows.map(row=>row.modelVersion)).size>1||new Set(rows.map(row=>row.category)).size>1)return{status:'not_comparable',requiresReview:false,automaticRetraining:false,message:'Compare one model version and prop category at a time.'};
 const dates=[...new Set(sorted.map(row=>row.eventStart))],split=dates[Math.floor(dates.length*2/3)],reference=sorted.filter(row=>row.eventStart<split),recent=sorted.filter(row=>row.eventStart>=split);
 if(reference.length<200||recent.length<100||new Set(reference.map(row=>row.gameId)).size<20||new Set(recent.map(row=>row.gameId)).size<10)return{status:'insufficient_evidence',requiresReview:false,automaticRetraining:false,message:'Insufficient independent chronological game coverage for a drift diagnostic.'};
 const frequencies=(group:ScoredPropObservation[])=>Array.from({length:10},(_,i)=>(group.filter(row=>Math.min(9,Math.floor(row.rawProbability*10))===i).length+.5)/(group.length+5));
 const a=frequencies(reference),b=frequencies(recent),psi=b.reduce((sum,p,i)=>sum+(p-a[i])*Math.log(p/a[i]),0),referenceMetrics=propProbabilityMetrics(reference.map(row=>({gameId:row.gameId,p:row.rawProbability,y:row.outcome})))!,recentMetrics=propProbabilityMetrics(recent.map(row=>({gameId:row.gameId,p:row.rawProbability,y:row.outcome})))!;
 const brierDeterioration=Boolean(referenceMetrics.brierInterval95&&recentMetrics.brierInterval95&&recentMetrics.brierInterval95[0]>referenceMetrics.brierInterval95[1]);
 return{status:'evaluated',requiresReview:psi>.25||brierDeterioration,automaticRetraining:false,psi,reference:referenceMetrics,recent:recentMetrics,brierDeterioration,message:'PSI0.25 is a declared distribution-shift heuristic, not a calibrated probability of model failure. Drift queues review; it never directly promotes or retrains a model.'};
}
