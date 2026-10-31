/** Prospective final-score auditing for game event contracts.
 * This module never settles a personal position or fits a player calibrator.
 * A resolution targets the SELECTED SIDE's full 100-cent payout, not an
 * inferred exchange payment. Partial tie payments remain separate evidence.
 */
import Decimal from 'decimal.js';
import {cloudClient} from '../cloud/context';
import {ApiError} from '../auth';
import {NFLVERSE_GAMES} from '../warehouse';
import {boundedFetch,normalizePublicSchedule,sha} from '../public-nfl/sources';
import {sharedCache,putCache,fresh} from '../public-nfl/store';
import {canonicalPropTeam} from './normalize';
import {propWrite} from './store';
import {GAME_MARKET_STATS,isGameMarket,type PropMarketContract} from './market-types';
import {comparePropThreshold,propProbabilityMetrics} from './evaluation';
import {valueProp} from './math';
import type {PublicGame} from '../public-nfl/types';

export const GAME_MARKET_AUDIT_PROTOCOL='game-contract-selected-side-full-payout-7.0.0';
const CACHE_KEY='game-markets-v7',TTL=15*60000,MAX_PREDICTIONS=50000,MAX_RESOLUTIONS=100000,MATURITY_MS=6*3600000;
type Row=Record<string,any>;
type Observation={predictionId:string;gameId:string;contractId:string;category:string;modelVersion:string;side:'YES'|'NO';p:number;y:0|1;eventStart:string;marketProbability:number|null};
let memory:{expiresAt:number;value:Row}|undefined,pending:Promise<Row>|undefined;
const stamp=(value:unknown)=>typeof value==='string'&&/(?:Z|[+-]\d{2}:\d{2})$/.test(value)&&Number.isFinite(Date.parse(value))?Date.parse(value):NaN;
const finite=(value:unknown):value is number=>typeof value==='number'&&Number.isFinite(value);
const nonempty=(value:unknown):value is string=>typeof value==='string'&&value.trim().length>0;
const num=(value:unknown)=>(typeof value==='number'||typeof value==='string'&&/^-?\d+(?:\.\d+)?$/.test(value))&&Number.isFinite(Number(value))?Number(value):NaN;
const https=(value:unknown)=>{try{return typeof value==='string'&&new URL(value).protocol==='https:';}catch{return false;}};
function contractOf(row:Row):PropMarketContract|null{
 const contract=row.contract??row.data?.contract??(row.captured_quote?.data?{...row.captured_quote.data,...row.contract_overlay}:null);
 return contract&&typeof contract==='object'?contract:null;
}
function predictionOf(row:Row){
 const contract=contractOf(row),sources=row.sources??row.data?.sources;
 return{id:row.id,contract,gameId:row.game_id??contract?.gameId,category:row.category??contract?.stat,
  side:row.side??row.data?.side,threshold:num(row.threshold??contract?.threshold),operator:row.operator??contract?.operator,
  raw:num(row.raw_probability??row.data?.probability?.raw),modelVersion:row.model_version??row.data?.modelVersion,
  inputVersion:row.input_version??row.data?.inputVersion,predictedAt:row.captured_at??row.data?.capturedAt,
  archivedAt:row.created_at,eventStart:row.event_start??contract?.eventStart,sources,
  retrospective:row.data?.retrospective===true};
}

/** A nullable player identity is intentional for game markets; never synthesize
 * a GSIS identity to route these forecasts into player-availability auditing. */
export function auditGameMarketPrediction(row:Row,now=new Date()):string[]{
 const p=predictionOf(row),c=p.contract,reasons:string[]=[];
 if(!c||!isGameMarket(p.category))return['unsupported_game_contract'];
 if(!nonempty(p.id)||!nonempty(c.id)||!nonempty(c.contractId)||!nonempty(c.eventId)||!nonempty(p.gameId)||!nonempty(p.modelVersion)||!nonempty(p.inputVersion))reasons.push('missing_prediction_identity');
 if(c.playerId!==null||c.mapping?.status!=='verified'||!c.subject||!['team','game'].includes(c.subject.kind))reasons.push('unverified_game_subject');
 if(!finite(p.raw)||p.raw<0||p.raw>1||!['YES','NO'].includes(p.side))reasons.push('invalid_selected_side_probability');
 if(!finite(p.threshold)||!['gt','gte','lt','lte','eq'].includes(p.operator)||c.stat!==p.category||c.threshold!==p.threshold||c.operator!==p.operator||c.gameId!==p.gameId||!nonempty(c.rulesHash))reasons.push('contract_definition_mismatch');
 if(!c.settlement?.rulesVerified||!c.settlement.modelCompatible||!c.settlement.fullGame||!c.settlement.overtimeIncluded||num(c.settlement.payoutCents)!==100)reasons.push('unverified_full_game_payout_rules');
 if(c.stat==='gameWinner'){
  const tie=num(c.settlement.tiePayoutCents);
  if(!finite(tie)||tie<0||tie>100||p.threshold!==0||p.operator!=='gt')reasons.push('unsupported_tie_settlement');
 }
 const predicted=stamp(p.predictedAt),archived=stamp(p.archivedAt),event=stamp(p.eventStart);
 if(![predicted,archived,event].every(Number.isFinite)||stamp(c.eventStart)!==event)reasons.push('missing_or_mismatched_timestamps');
 else{
  if(predicted>=event||archived>=event)reasons.push('not_archived_before_kickoff');
  if(archived<predicted||predicted>now.getTime()+60000||archived>now.getTime()+60000)reasons.push('invalid_archive_chronology');
 }
 if(!Array.isArray(p.sources)||!p.sources.length||p.sources.some((s:Row)=>!Number.isFinite(stamp(s.collectedAt??s.checkedAt))||stamp(s.collectedAt??s.checkedAt)>predicted))reasons.push('unverified_pre_prediction_input_availability');
 if(p.retrospective)reasons.push('retrospective_import');
 return reasons;
}

/** This is research final-score resolution under normal completion, not
 * verification that a platform paid a contract or accepted a real order. */
export function resolveGameMarketResearch(row:Row,game:PublicGame,source:{url:string;version:string;checkedAt:string},now=new Date()):Row{
 const p=predictionOf(row),c=p.contract;
 const unavailable=(reason:string)=>({status:'unresolved',observedValue:null,outcomeBasis:'selected_side_full_payout',exchangeSettlementVerified:false,reason});
 const audit=auditGameMarketPrediction(row,now);if(audit.length)return unavailable(audit.join(', '));
 if(!c||game.id!==p.gameId||Date.parse(game.startTime)!==Date.parse(p.eventStart))return unavailable('final_game_identity_mismatch');
 if(!https(source.url)||!nonempty(source.version)||!Number.isFinite(stamp(source.checkedAt))||stamp(source.checkedAt)<stamp(p.eventStart)||stamp(source.checkedAt)>now.getTime()+60000)return unavailable('unverified_final_score_provenance');
 if(game.status!=='final'||stamp(game.startTime)>now.getTime()-MATURITY_MS)return unavailable('final_game_not_mature');
 const home=game.home.score,away=game.away.score;
 if(!Number.isInteger(home)||!Number.isInteger(away)||home!<0||away!<0)return unavailable('verified_final_scores_unavailable');
 const team=canonicalPropTeam(c.subject?.teamId??c.team),isHome=team===canonicalPropTeam(game.home.id),isAway=team===canonicalPropTeam(game.away.id);
 if(c.stat!=='totalPoints'&&(!isHome&&!isAway||c.subject?.kind!=='team'))return unavailable('final_team_identity_mismatch');
 if(c.stat!=='totalPoints'&&(canonicalPropTeam(c.team)!==team||canonicalPropTeam(c.opponent)!==canonicalPropTeam(isHome?game.away.id:game.home.id)))return unavailable('final_team_or_opponent_mismatch');
 if(c.stat==='totalPoints'&&c.subject?.kind!=='game')return unavailable('final_game_subject_mismatch');
 const value=c.stat==='totalPoints'?home!+away!:c.stat==='teamTotal'?(isHome?home!:away!):(isHome?home!-away!:away!-home!);
 let full:boolean,partialPayoutCents:string|null=null;
 if(c.stat==='gameWinner'&&value===0){const tie=new Decimal(c.settlement.tiePayoutCents!),payout=p.side==='YES'?tie:new Decimal(100).sub(tie);full=payout.eq(100);if(payout.gt(0)&&payout.lt(100))partialPayoutCents=payout.toString();}
 else{const yes=comparePropThreshold(value,p.threshold,p.operator);full=p.side==='YES'?yes:!yes;}
 return{status:full?'yes':'no',observedValue:value,outcomeBasis:'selected_side_full_payout',selectedSide:p.side,
  gameId:p.gameId,contractId:c.id,category:p.category,threshold:p.threshold,operator:p.operator,
  actualFullPayoutHit:Number(full),partialPayoutCents,exchangeSettlementVerified:false,
  finalScores:{home:home!,away:away!,homeTeam:game.home.id,awayTeam:game.away.id},
  finalScoreSignature:sha({gameId:game.id,home:home!,away:away!,startTime:new Date(game.startTime).toISOString(),rulesHash:c.rulesHash,side:p.side}),
  reason:'Verified final NFL scores compared with the frozen selected-side full-payout definition under normal completion. Exceptional exchange settlements and actual financial payouts remain unverified.'};
}

function latestResolutionChains(rows:Row[]){
 const groups=new Map<string,Row[]>();for(const row of rows){const id=row.prediction_id??row.predictionId??row.data?.predictionId,list=groups.get(id)??[];list.push(row);groups.set(id,list);}
 const result=new Map<string,{row:Row|null;error?:string}>();
 for(const[id,list]of groups){list.sort((a,b)=>stamp(a.resolved_at??a.resolvedAt)-stamp(b.resolved_at??b.resolvedAt)||String(a.id).localeCompare(String(b.id)));let previous:Row|null=null,error:string|undefined;const seen=new Set<string>();
  for(const row of list){const data=row.data??row,prev=row.previous_resolution_id??data.previousResolutionId,at=stamp(row.resolved_at??data.resolvedAt);
   if(!nonempty(row.id)||seen.has(row.id)||!Number.isFinite(at)){error='invalid_resolution_identity';break;}seen.add(row.id);
   if(previous?(prev!==previous.id||at<=stamp(previous.resolved_at??previous.data?.resolvedAt??previous.resolvedAt)):Boolean(prev)){error='ambiguous_resolution_correction';break;}previous=row;
  }result.set(id,{row:error?null:previous,error});
 }return result;
}
function benchmark(row:Row):number|null{
 const p=predictionOf(row),c=p.contract;if(!c)return null;
 if(c.stat==='gameWinner'&&num(c.settlement.tiePayoutCents)>0&&num(c.settlement.tiePayoutCents)<100)return null;
 const observed=stamp(c.observedAt),predicted=stamp(p.predictedAt);
 if(!Number.isFinite(observed)||observed>predicted||predicted-observed>120000)return null;
 try{return valueProp(c,p.side,.5).breakEven;}catch{return null;}
}
function metrics(rows:Observation[]){
 const raw=propProbabilityMetrics(rows.map(row=>({gameId:row.gameId,p:row.p,y:row.y}))),common=rows.filter(row=>row.marketProbability!==null);
 return{n:rows.length,games:new Set(rows.map(row=>row.gameId)).size,contracts:new Set(rows.map(row=>row.contractId)).size,
  raw,calibrated:null,market:propProbabilityMetrics(common.map(row=>({gameId:row.gameId,p:row.marketProbability!,y:row.y}))),
  marketComparison:{commonSampleSize:common.length,rawOnCommon:propProbabilityMetrics(common.map(row=>({gameId:row.gameId,p:row.p,y:row.y}))),marketOnCommon:propProbabilityMetrics(common.map(row=>({gameId:row.gameId,p:row.marketProbability!,y:row.y})))}};
}
function grouped(rows:Observation[],key:(row:Observation)=>string){const groups=new Map<string,Observation[]>();for(const row of rows){const name=key(row),list=groups.get(name)??[];list.push(row);groups.set(name,list);}return Object.fromEntries([...groups].map(([name,list])=>[name,metrics(list)]));}

/** Pure aggregator: NO predictions are scored against their own target. A
 * fifty-cent tie is a zero full-payout hit for both sides, never 1 - YES. */
export function evaluateGameMarketHistory(predictions:Row[],resolutions:Row[],now=new Date()):Row{
 const latest=latestResolutionChains(resolutions),observations:Observation[]=[],excluded:Record<string,number>={};let eligible=0,unresolved=0,partialTieObservations=0;
 const exclude=(reason:string)=>{excluded[reason]=(excluded[reason]??0)+1;};
 for(const row of predictions){const p=predictionOf(row),audit=auditGameMarketPrediction(row,now);if(audit.length){audit.forEach(exclude);continue;}
  if(stamp(p.eventStart)>now.getTime()-MATURITY_MS){exclude('event_not_mature');continue;}eligible++;
  const chain=latest.get(p.id),r=chain?.row,data=r?.data??r;
  if(chain?.error){exclude(chain.error);unresolved++;continue;}
  if(!r||!data||data.outcomeBasis!=='selected_side_full_payout'||data.selectedSide!==p.side){exclude('matching_selected_side_resolution_unavailable');unresolved++;continue;}
  const resolvedAt=stamp(r.resolved_at??data.resolvedAt),availableAt=stamp(r.available_at??data.availableAt),status=r.status??data.status;
  if(!['yes','no'].includes(status)||!(r.verified_final??data.verifiedFinal)||data.rulesHash!==p.contract!.rulesHash||!https(r.source_url??data.sourceUrl)||!nonempty(r.source_version??data.sourceVersion)||![resolvedAt,availableAt].every(Number.isFinite)||resolvedAt<stamp(p.eventStart)||availableAt<stamp(p.eventStart)||availableAt>now.getTime()+60000||resolvedAt>now.getTime()+60000){exclude('unverified_final_resolution');unresolved++;continue;}
  const score=data.finalScores;
  if(data.gameId!==p.gameId||data.contractId!==p.contract!.id||data.category!==p.category||data.threshold!==p.threshold||data.operator!==p.operator||!score){exclude('resolution_contract_identity_mismatch');unresolved++;continue;}
  const finalGame={id:p.gameId,startTime:p.eventStart,status:'final',season:Number(p.gameId.slice(0,4)),week:Number(p.gameId.split('_')[1]),home:{id:score.homeTeam,name:score.homeTeam,abbreviation:score.homeTeam,score:score.home},away:{id:score.awayTeam,name:score.awayTeam,abbreviation:score.awayTeam,score:score.away},sources:[]} as PublicGame;
  const checked=resolveGameMarketResearch(row,finalGame,{url:r.source_url??data.sourceUrl,version:r.source_version??data.sourceVersion,checkedAt:r.available_at??data.availableAt},now);
  if(checked.status!==status||checked.observedValue!==num(r.observed_value??data.observedValue)||checked.actualFullPayoutHit!==data.actualFullPayoutHit||checked.finalScoreSignature!==data.finalScoreSignature||checked.partialPayoutCents!==data.partialPayoutCents){exclude('inconsistent_final_score_resolution');unresolved++;continue;}
  const outcome=status==='yes'?1:0;if(data.actualFullPayoutHit!==outcome){exclude('inconsistent_full_payout_outcome');unresolved++;continue;}
  if(data.partialPayoutCents!==null&&data.partialPayoutCents!==undefined)partialTieObservations++;
  observations.push({predictionId:p.id,gameId:p.gameId,contractId:p.contract!.id,category:p.category,modelVersion:p.modelVersion,side:p.side,p:p.raw,y:outcome,eventStart:p.eventStart,marketProbability:benchmark(row)});
 }
 return{protocol:GAME_MARKET_AUDIT_PROTOCOL,status:observations.length?'research_only':'insufficient_evidence',updatedAt:now.toISOString(),
  scope:'Prospective game-contract selected-side full 100-cent payout under normal completion; separate from player participation, calibrated models and private financial P/L.',
  outcomeBasis:'selected_side_full_payout',totalSnapshots:predictions.length,sampleSize:observations.length,eligibleResolved:observations.length,
  coverage:{eligibleMaturePredictions:eligible,resolvedPredictions:observations.length,unresolvedPredictions:unresolved,complete:unresolved===0,maturityHours:6},
  partialTieObservations,excludedCounts:excluded,overall:metrics(observations),byCategory:grouped(observations,row=>row.category),byModelVersion:grouped(observations,row=>row.modelVersion),byDate:grouped(observations,row=>new Date(row.eventStart).toISOString().slice(0,10)),
  windows:{days7:metrics(observations.filter(row=>stamp(row.eventStart)>=now.getTime()-7*86400000)),days30:metrics(observations.filter(row=>stamp(row.eventStart)>=now.getTime()-30*86400000)),allTime:metrics(observations)},
  calibratedSampleSize:0,calibratedProbabilitiesAvailable:false,calibrationStatus:'No independently validated game-contract calibration/promotion protocol has been approved.',
  message:observations.length?'Selected-side full-payout events are scored from verified final NFL scores without rewriting any forecast. This is a conditional research audit, not proof of an exchange settlement.':'Insufficient verified prospective game-contract outcomes. Missing metrics and calibration remain unavailable.',
  limitations:['Repeated snapshots and related contracts are correlated within games; game-block intervals require at least eight game blocks and do not cover source or model errors.',
   'A 50-cent tie payment is not a full-payout hit. Raw probabilities and NO targets are not complemented across partial-payout events.',
   'Market baselines require verified captured costs and binary payout compatibility; an exchange price alone does not identify full-payout probability when partial ties are possible.',
   'Game finality and exact thresholds resolve research outcomes only. Discretionary cancellation, forfeit and actual financial payouts require verified platform settlement evidence.',
   'No game calibrator is fitted or promoted, and personal wagers, balances and ledgers are never read or written.']};
}

async function gameArchive(){
 const rows:Row[]=[];let total:number|null=null;
 const columns='id,game_id,category,side,threshold,operator,raw_probability,model_version,input_version,captured_at,created_at,event_start,contract:data->contract,contract_overlay:data->contractOverlay,captured_quote:shared_prop_quotes!shared_prop_snapshots_quote_id_fkey(data),sources:data->sources';
 for(let offset=0;offset<MAX_PREDICTIONS;){const response=await cloudClient().from('shared_prop_snapshots').select(columns,{count:'exact'}).in('category',[...GAME_MARKET_STATS]).not('raw_probability','is',null).order('id').range(offset,offset+499);
  if(response.error)throw new ApiError('Game prediction archive unavailable.',503);const page=response.data??[];if(total===null)total=response.count??null;else if(total!==response.count)throw new ApiError('The game prediction archive changed during the audit.',409);
  rows.push(...page);offset+=page.length;if(total!==null&&offset>=total)return rows;if(!page.length)break;
 }throw new ApiError('The complete game prediction archive requires partitioning; no capped subset was scored.',413);
}
async function matchingResolutions(ids:string[]){
 const rows:Row[]=[];
 for(let start=0;start<ids.length;start+=200){let count:number|null=null;
  for(let offset=0;offset<MAX_RESOLUTIONS;){const response=await cloudClient().from('shared_prop_resolutions').select('*',{count:'exact'}).in('prediction_id',ids.slice(start,start+200)).order('id').range(offset,offset+499);
   if(response.error)throw new ApiError('Game resolution history unavailable.',503);const page=response.data??[];if(count===null)count=response.count??null;else if(count!==response.count)throw new ApiError('Game resolution history changed during the audit.',409);
   rows.push(...page);if(rows.length>MAX_RESOLUTIONS)throw new ApiError('Game resolution history requires explicit partitioning.',413);offset+=page.length;if(count!==null&&offset>=count)break;if(!page.length)throw new ApiError('Complete game resolution coverage unavailable.',503);
  }
 }return rows;
}

/** Cache-only interactive read: never scans an unbounded history or mutates
 * source outcomes simply because someone opens the NFL dashboard. */
export async function getGameMarketPerformance():Promise<Row>{
 if(memory&&memory.expiresAt>Date.now())return memory.value;
 try{const saved=await sharedCache('performance',CACHE_KEY);
  if(saved?.data){const value=fresh(saved)?saved.data:{...saved.data,status:'stale',message:'The saved game-market audit retains its original evaluation time; a background refresh is pending.'};memory={value,expiresAt:Date.now()+(fresh(saved)?TTL:60000)};return value;}
  return{status:'pending',sampleSize:null,eligibleResolved:null,overall:null,updatedAt:null,protocol:GAME_MARKET_AUDIT_PROTOCOL,calibratedProbabilitiesAvailable:false,message:'Prospective game-market evaluation is pending the scheduled final-score audit. No accuracy or calibration was invented.'};
 }catch{return{status:'unavailable',sampleSize:null,eligibleResolved:null,overall:null,updatedAt:null,protocol:GAME_MARKET_AUDIT_PROTOCOL,calibratedProbabilitiesAvailable:false,message:'Saved game-market evaluation could not be retrieved. Existing records remain preserved.'};}
}

/** Background-only reconciliation. Appends source corrections and a compact
 * aggregate; no old snapshot, resolution, user record or model is overwritten. */
export async function refreshGameMarketAudit():Promise<Row>{
 if(pending)return pending;
 pending=(async()=>{try{
  const predictions=await gameArchive(),resolutions=await matchingResolutions(predictions.map(row=>row.id)),latest=latestResolutionChains(resolutions),now=new Date(),updates:Row[]=[];
  const past=predictions.filter(row=>!auditGameMarketPrediction(row,now).length&&stamp(predictionOf(row).eventStart)<=now.getTime()-MATURITY_MS);
  if(past.length){const response=await boundedFetch(NFLVERSE_GAMES,5_000_000,15000),raw=response.body.toString('utf8'),source={url:NFLVERSE_GAMES,version:sha(response.body),checkedAt:now.toISOString()},seasons=[...new Set(past.map(row=>Number(predictionOf(row).gameId.slice(0,4))))];
   if(seasons.length>5)throw new ApiError('Partition more than five game-audit seasons explicitly.',413);const games=new Map<string,PublicGame>();for(const season of seasons)for(const game of normalizePublicSchedule(raw,source.checkedAt,season).games)games.set(game.id,game);
   for(const row of past){const p=predictionOf(row),game=games.get(p.gameId),chain=latest.get(p.id);if(!game||chain?.error)continue;
    const outcome=resolveGameMarketResearch(row,game,source,now);if(outcome.status==='unresolved')continue;const previous=chain?.row,old=previous?.data??previous;
    if(old?.outcomeBasis==='selected_side_full_payout'&&old.finalScoreSignature===outcome.finalScoreSignature)continue;
    const resolvedAt=new Date(Math.max(now.getTime(),previous?stamp(previous.resolved_at??old?.resolvedAt)+1:0)).toISOString();
    updates.push({...outcome,id:'game-resolution-'+sha([p.id,outcome.finalScoreSignature,source.version,previous?.id??null]),predictionId:p.id,
     rulesHash:p.contract!.rulesHash,resolvedAt,availableAt:source.checkedAt,sourceUrl:source.url,sourceVersion:source.version,verifiedFinal:true,previousResolutionId:previous?.id??null});
   }
  }
  const written:Row[]=[];
  for(let offset=0;offset<updates.length;offset+=500){const batch=updates.slice(offset,offset+500),stored=await propWrite({action:'resolutions_put',resolutions:batch});
   if(!Array.isArray(stored)||stored.length!==batch.length||stored.some((row:Row,index:number)=>row.id!==batch[index].id))throw new ApiError('The final-score resolution writes could not be confirmed. Prior immutable records remain preserved.',503);
   written.push(...stored);
  }
  const performance=evaluateGameMarketHistory(predictions,[...resolutions,...written],now);await putCache('performance',CACHE_KEY,performance,sha(performance),TTL);
  memory={value:performance,expiresAt:Date.now()+TTL};return{status:'completed',checkedAt:now.toISOString(),researchResolutionsAppended:written.length,resolutionWriteMeaning:'Idempotent writes confirmed by the database; a concurrent already-stored identity may be returned.',performance,personalWagersSettled:0,modelsPromoted:0};
 }catch(error){return{status:'failed',checkedAt:new Date().toISOString(),researchResolutionsAppended:null,personalWagersSettled:0,modelsPromoted:0,message:error instanceof ApiError?error.message:'The complete game-market audit could not be verified. Prior forecasts, outcomes and cached metrics remain preserved.'};}
 finally{pending=undefined;}})();return pending;
}
