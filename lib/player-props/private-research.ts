import {randomUUID,timingSafeEqual} from 'node:crypto';
import Decimal from 'decimal.js';
import {after} from 'next/server';
import {z} from 'zod';
import {ApiError} from '../auth';
import {requireCloudUser,cloudError,type CloudContext} from '../cloud/context';
import {record,records,saveRecord,finiteJson} from '../cloud/store';
import {encodeCloudData} from '../cloud/codec';
import {attestCloudInput,attestCloudResult,cloudInputMac,verifyCloudResult,canonicalJson} from '../cloud/attestation';
import {publicGameDetail} from '../public-nfl/service';
import {sharedWrite} from '../public-nfl/store';
import {sha} from '../public-nfl/sources';
import {recheckPropMarketFreshness} from './normalize';
import type {PropMarketContract} from './market-types';
import type {PropResearch} from './types';

const KIND='prop_hypothetical_jobs',RESEARCH_ID=z.string().regex(/^[a-f0-9]{64}$/),COUNTS=z.union([z.literal(10000),z.literal(50000),z.literal(100000)]).default(10000);
const money=z.string().regex(/^\d{1,9}(?:\.\d{1,2})?$/);
const offerSchema=z.object({verified:z.literal(true),source:z.string().min(3).max(1000),quotedAt:z.string().datetime({offset:true}),totalStake:money,combinedPayout:money,fees:money,settlementRules:z.string().min(20).max(4000),settlementComplete:z.literal(true)}).strict();
const combinationSchema=z.object({researchIds:z.array(RESEARCH_ID).min(2).max(12),sides:z.record(RESEARCH_ID,z.enum(['YES','NO'])).optional(),simulations:COUNTS,offer:offerSchema.optional()}).strict();
const scenarioSchema=z.object({gameId:z.string().min(5).max(80),playerId:z.string().min(1).max(180),status:z.enum(['active','limited','inactive']),researchIds:z.array(RESEARCH_ID).max(12).default([]),simulations:COUNTS}).strict();
type ResearchKind='combination'|'what_if';
type Job=Record<string,any>&{id:string;kind:ResearchKind;status:string;input:Record<string,any>;result:Record<string,any>|null};
const stableHash=(value:unknown)=>sha(canonicalJson(value));

function verifyInput(ctx:CloudContext,id:string,job:Job){
 const proof=job.inputProof;
 if(proof?.version!==1||proof.algorithm!=='hmac-sha256'||typeof proof.mac!=='string'||!/^[a-f0-9]{64}$/.test(proof.mac))throw new ApiError('Private research inputs have no verified server provenance. The original record remains saved.',422);
 const expected=Buffer.from(cloudInputMac(ctx,id,job.input),'hex'),actual=Buffer.from(proof.mac,'hex');
 if(!timingSafeEqual(expected,actual))throw new ApiError('Private research inputs were changed outside the verified research workflow. No simulation was run.',422);
 if(job.kind!==job.input.kind||job.id!==id)throw new ApiError('Private research identity does not match its signed inputs.',422);
}
function safeOutput(ctx:CloudContext,id:string,job:Job):Job&{provenanceVerified:boolean;hypothetical:boolean;actualWagerRecorded:boolean}{verifyInput(ctx,id,job);if(job.status==='completed'){verifyCloudResult(ctx,id,job);return{...job,provenanceVerified:true,hypothetical:true,actualWagerRecorded:false};}return{...job,provenanceVerified:false,hypothetical:true,actualWagerRecorded:false};}
async function cas(ctx:CloudContext,id:string,oldStatus:string,next:Job,lease?:string){
 let query=ctx.client.from('gridiron_records').update({data:encodeCloudData(finiteJson(next)),updated_at:new Date().toISOString()}).eq('user_id',requireCloudUser(ctx).id).eq('id',id).eq('kind',KIND).eq('data->>status',oldStatus);
 if(lease)query=query.eq('data->>lease',lease);
 const result=await query.select('id');if(result.error)cloudError(result.error);return Boolean(result.data?.length);
}
function sourceVersions(sources:unknown){
 if(!Array.isArray(sources))throw new ApiError('The baseline lacks reproducible source versions. Refresh the game analysis first.',422);
 const versions:Record<string,{status:string;version:string|null}>={};
 for(const source of sources){if(!source||typeof source.id!=='string'||!source.id.startsWith('nflverse-'))continue;const status=source.status??'unknown';if(status==='available'&&(typeof source.version!=='string'||!source.version))throw new ApiError('An available baseline source lacks a content version. Refresh the analysis first.',422);versions[source.id]={status,version:status==='available'?source.version:null};}
 if(!versions['nflverse-pbp']?.version||!versions['nflverse-rosters']?.version)throw new ApiError('Play-by-play and roster source versions are required before comparing private scenarios.',422);
 return Object.fromEntries(Object.entries(versions).sort(([a],[b])=>a.localeCompare(b)));
}
function definition(contract:PropMarketContract){
 if(contract.operator==='eq')throw new ApiError('Exact-equality contracts are not supported by the joint full-game engine. No replacement threshold was guessed.',422);
 return{id:contract.id,kind:'player',playerId:contract.playerId,stat:contract.stat,threshold:contract.threshold,direction:['gt','gte'].includes(contract.operator)?'over':'under',equality:['gte','lte'].includes(contract.operator)?'yes':'no',period:'full_game_including_overtime',...(contract.stat==='touchdowns'?{touchdownScope:'offensive_rushing_receiving_only'}:{})};
}
function sameDefinition(first:PropMarketContract,second:PropMarketContract){return ['id','contractId','eventId','gameId','eventStart','playerId','team','opponent','stat','threshold','operator','rulesHash'].every(key=>(first as any)[key]===(second as any)[key]);}
function validateOffer(offer:Record<string,any>){
 const stake=new Decimal(offer.totalStake),fee=new Decimal(offer.fees),at=Date.parse(offer.quotedAt);
 if(stake.lte(0)||fee.gt(stake)||at>Date.now()+60000||Date.now()-at>120000)throw new ApiError('The combined offer has invalid money or a stale observation time.',422);
}
async function loadSelected(ctx:CloudContext,ids:string[]){
 if(new Set(ids).size!==ids.length)throw new ApiError('Choose distinct saved research records.',422);
 if(!ids.length)return[] as PropResearch[];
 const response=await ctx.client.from('shared_prop_snapshots').select('id,data').in('id',ids);if(response.error)cloudError(response.error);
 const rows=ids.map(id=>(response.data??[]).find(row=>row.id===id)?.data as PropResearch|undefined);
 if(rows.some(row=>!row))throw new ApiError('One or more published player research records could not be found.',404);
 const contracts=rows.map(row=>row!.contract.id);if(new Set(contracts).size!==contracts.length)throw new ApiError('Choose 2–12 distinct contracts, rather than both sides of the same contract.',422);
 const current=await ctx.client.from('shared_prop_contracts').select('id,data').in('id',contracts);if(current.error)cloudError(current.error);
 return rows.map(row=>{
  const original=row!,stored=(current.data??[]).find(item=>item.id===original.contract.id)?.data as PropMarketContract|undefined;
  if(!stored||!sameDefinition(original.contract,stored))throw new ApiError('A selected contract no longer matches its saved player, threshold or settlement rules.',422);
  const contract=recheckPropMarketFreshness(stored);
  if(!contract.verification.current||!contract.verification.quoteVerified)throw new ApiError('A selected quote is no longer fresh. Refresh Player Props before saving this private research.',422);
  if(contract.mapping.status!=='verified'||!contract.playerId||!contract.settlement.rulesVerified||!contract.settlement.modelCompatible||!contract.settlement.fullGame||!contract.settlement.overtimeIncluded)throw new ApiError('A selected player identity or full-game settlement rule is not supported.',422);
  if(contract.stat==='touchdowns'&&/return|defens|special.team/i.test(contract.settlement.statCoverage))throw new ApiError('Return or defensive touchdown settlement is outside this offensive player model.',422);
  if(original.stale||!['available','conditional'].includes(original.status)||original.probability.raw===null)throw new ApiError('A selected research record is stale or lacks a supported model probability.',422);
  if(Date.parse(contract.eventStart)<=Date.now())throw new ApiError('Private pregame research must be requested before kickoff.',409);
  return{...original,contract};
 });
}

/** Saved private selections never enter the shared/public compute reservation. */
export async function queuePrivatePropResearch(ctx:CloudContext,kind:ResearchKind,input:unknown){
 requireCloudUser(ctx);if(!ctx.accessToken)throw new ApiError('A verified app session is required for private research.',401);
 if(kind!=='combination'&&kind!=='what_if')throw new ApiError('Choose combination or what-if research.',422);
 const values=kind==='combination'?combinationSchema.parse(input):scenarioSchema.parse(input);
 if(kind==='combination'&&(values as z.infer<typeof combinationSchema>).offer)validateOffer((values as z.infer<typeof combinationSchema>).offer!);
 const selected=await loadSelected(ctx,values.researchIds),gameId=kind==='what_if'?(values as z.infer<typeof scenarioSchema>).gameId:selected[0].game.id;
 if(selected.some(row=>row.game.id!==gameId))throw new ApiError('Joint research requires contracts from the same complete simulated game. Cross-game independence is not assumed.',422);
 const detail=await publicGameDetail(gameId),baseline=detail.analysis;
 if(detail.game.id!==gameId||Date.parse(detail.game.startTime)<=Date.now())throw new ApiError('Choose a verified upcoming NFL game.',409);
 if(!baseline||baseline.status!=='completed'||baseline.stale||!baseline.result)throw new ApiError('A fresh completed game analysis is required before private scenario comparisons.',422);
 if(selected.some(row=>row.simulationId!==baseline.id))throw new ApiError('The selected prediction used an older simulation. Refresh Player Props before comparing it.',422);
 const versions=sourceVersions(baseline.research?.sources);
 if(kind==='what_if'){
  const scenario=values as z.infer<typeof scenarioSchema>;
  if(!(baseline.research?.playerCatalog??[]).some((player:any)=>player.id===scenario.playerId))throw new ApiError('The hypothetical player is not on the latest verified matchup roster.',422);
 }
 const sides=kind==='combination'?(values as z.infer<typeof combinationSchema>).sides??{}:{};
 if(Object.keys(sides).some(id=>!values.researchIds.includes(id)))throw new ApiError('A side override must reference a selected research record.',422);
 const selections=selected.map(row=>{const side=sides[row.id]??row.side;return{researchId:row.id,contract:row.contract,side,baselineProbability:side===row.side?row.probability.raw:1-row.probability.raw!};});
 const id=randomUUID(),quotaId=randomUUID(),nonce=randomUUID(),now=new Date().toISOString();
 const game={id:detail.game.id,home:detail.game.home.id,away:detail.game.away.id,startTime:detail.game.startTime,season:detail.game.season,week:detail.game.week};
 const frozen=finiteJson({kind,game,simulations:values.simulations,selections,contractDefinitions:selections.map(row=>definition(row.contract)),selectedOutcomes:kind==='combination'?Object.fromEntries(selections.map(row=>[row.contract.id,row.side.toLowerCase()])):null,
  whatIf:kind==='what_if'?{playerId:(values as z.infer<typeof scenarioSchema>).playerId,status:(values as z.infer<typeof scenarioSchema>).status}:null,
  offer:kind==='combination'?(values as z.infer<typeof combinationSchema>).offer??null:null,
  context:{injuries:detail.injuries,weather:detail.weather},baseline:{id:baseline.id,modelVersion:baseline.result.modelVersion,evidenceVersions:versions,homeWinProbability:baseline.result.homeWinProbability,awayWinProbability:baseline.result.awayWinProbability,tieProbability:baseline.result.tieProbability,simulations:baseline.result.simulations},quotaId,quotaKey:gameId+'::private_research::'+nonce});
 await sharedWrite({action:'job_enqueue',id:quotaId,gameId:frozen.quotaKey,inputHash:sha(nonce),data:{simulations:values.simulations,purpose:'private_research',game}});
 const job:Job={id,kind,status:'queued',createdAt:now,updatedAt:now,input:frozen,inputProof:attestCloudInput(ctx,id,frozen),result:null,error:null};
 await saveRecord(ctx,KIND,job,{id,entityKey:gameId,source:'GRIDIRON private hypothetical research'});
 after(async()=>{await executePrivatePropResearch(ctx,id).catch(()=>{});});
 return safeOutput(ctx,id,job);
}

function offerValue(offer:Record<string,any>|null,selections:any[],combination:Record<string,any>){
 const unavailable={netExpectedValueCents:null,theoreticalPayout:null,offerVerified:false,executionVerified:false,reason:'No verified combined offer was supplied. Individual contract asks are never multiplied into a supposed parlay quote.'};
 if(!offer)return unavailable;
 const stake=new Decimal(offer.totalStake),payout=new Decimal(offer.combinedPayout),fees=new Decimal(offer.fees),quoteTime=Date.parse(offer.quotedAt);
 if(stake.lte(0)||fees.gt(stake)||quoteTime>Date.now()+60000)throw new ApiError('The combined offer has invalid money or observation time.',422);
 if(Date.now()-quoteTime>120000)return{...unavailable,theoreticalPayout:offer.combinedPayout,offer,reason:'The combined offer expired while research ran. Its historical payout is retained, but current fee-aware value is withheld.'};
 const base={...unavailable,theoreticalPayout:offer.combinedPayout,offerVerified:true,offer,amountMeaning:'Total stake is all cash debited including the stated entry fees. Combined payout is total cash returned net of settlement costs; fees are not deducted a second time.'};
 if(selections.some(row=>!row.contract.settlement.unconditionalValuationSupported)||combination.pushAffectedProbability!==0)return{...base,reason:'Non-participation, exceptional settlement or push payouts are not fully modeled. Unconditional fee-aware expected value is withheld.'};
 return{...base,netExpectedValueCents:payout.mul(combination.jointProbability).sub(stake).mul(100).toFixed(8),reason:'Hypothetical expected cash return using the explicitly verified combined-product quote and its total actual costs. This does not verify availability, execution or a sportsbook parlay.'};
}
function checkedEngine(input:Record<string,any>,engine:Record<string,any>){
 if(Date.parse(input.game.startTime)<=Date.now())throw new ApiError('Kickoff occurred during private research. No new pregame probabilities were published.',409);
 const result=engine.result;
 if(!result||result.simulations!==input.simulations||result.home!==input.game.home||result.away!==input.game.away)throw new ApiError('The worker returned a different game or count. Private probabilities were withheld.',502);
 for(const team of [input.game.home,input.game.away]){const histogram=result.scoreDistributions?.[team]?.histogram;if(!Array.isArray(histogram)||histogram.some((row:any)=>!Number.isInteger(row.count)||row.count<0||!Number.isInteger(row.value)||row.value<0)||histogram.reduce((sum:number,row:any)=>sum+row.count,0)!==input.simulations)throw new ApiError('Complete-game score counts failed reconciliation.',502);}
 if(stableHash(sourceVersions(engine.research?.sources))!==stableHash(input.baseline.evidenceVersions)||result.modelVersion!==input.baseline.modelVersion)throw new ApiError('Underlying NFL evidence or model version changed while this research ran. Refresh the baseline before attributing any probability change to the scenario.',422);
 for(const definition of input.contractDefinitions){const calculated=result.contracts?.find((row:any)=>row.id===definition.id);if(!calculated)throw new ApiError('A selected contract was withheld by the engine. No unsupported joint probability was published.',422);if(!calculated.settlement||stableHash(calculated.settlement)!==stableHash(definition))throw new ApiError('The simulated contract threshold or settlement definition changed. Results were withheld.',502);}
 if(input.contractDefinitions.length){
  const rows=result.jointOutcomes,contracts=result.contracts;
  if(!Array.isArray(rows)||!Array.isArray(contracts)||contracts.length!==input.contractDefinitions.length||rows.some((row:any)=>!Number.isInteger(row.count)||row.count<0||!Array.isArray(row.outcomes)||row.outcomes.length!==contracts.length||row.outcomes.some((value:any)=>!['yes','no','push'].includes(value)))||rows.reduce((sum:number,row:any)=>sum+row.count,0)!==input.simulations)throw new ApiError('Shared-game joint outcome counts did not reconcile every simulated game.',502);
  for(const [index,contract]of contracts.entries()){
   const p=rows.filter((row:any)=>row.outcomes[index]==='yes').reduce((sum:number,row:any)=>sum+row.count,0)/input.simulations,push=rows.filter((row:any)=>row.outcomes[index]==='push').reduce((sum:number,row:any)=>sum+row.count,0)/input.simulations;
   if(!Number.isFinite(contract.probability)||!Number.isFinite(contract.pushProbability)||Math.abs(contract.probability-p)>1e-12||Math.abs(contract.pushProbability-push)>1e-12)throw new ApiError('A selected marginal probability disagrees with its shared-game outcomes.',502);
  }
  if(input.kind==='combination'){
   const selected=Object.entries(input.selectedOutcomes),indexes=selected.map(([key])=>contracts.findIndex((contract:any)=>contract.id===key));
   const hits=rows.filter((row:any)=>indexes.every((index:number,j:number)=>row.outcomes[index]===selected[j][1])).reduce((sum:number,row:any)=>sum+row.count,0),expected=hits/input.simulations;
   if(!result.combination||Math.abs(result.combination.jointProbability-expected)>1e-12)throw new ApiError('The reported joint estimate disagrees with its aligned full-game outcomes.',502);
   const independent=indexes.reduce((product:number,index:number,j:number)=>product*rows.filter((row:any)=>row.outcomes[index]===selected[j][1]).reduce((sum:number,row:any)=>sum+row.count,0)/input.simulations,1);
   if(!Number.isFinite(result.combination.independenceAssumptionProbability)||Math.abs(result.combination.independenceAssumptionProbability-independent)>1e-12)throw new ApiError('The independence comparison does not match the selected marginal outcomes.',502);
   const push=rows.filter((row:any)=>indexes.some((index:number)=>row.outcomes[index]==='push')).reduce((sum:number,row:any)=>sum+row.count,0)/input.simulations;
   if(!Number.isFinite(result.combination.pushAffectedProbability)||Math.abs(result.combination.pushAffectedProbability-push)>1e-12)throw new ApiError('Push settlement outcomes do not reconcile with the combination.',502);
  }
 }
 if(input.kind==='combination'){
  const combination=result.combination;
  if(!combination||!Number.isFinite(combination.jointProbability)||combination.jointProbability<0||combination.jointProbability>1||combination.simulations!==input.simulations||stableHash(combination.selectedOutcomes)!==stableHash(input.selectedOutcomes))throw new ApiError('Aligned selected-leg outcomes could not be verified.',502);
  return{kind:'combination',game:input.game,simulations:result.simulations,modelVersion:result.modelVersion,combination,valuation:offerValue(input.offer,input.selections,combination),conditional:input.selections.some((row:any)=>!row.contract.settlement.unconditionalValuationSupported),probabilityBasis:'Conditional on modeled participation and normal game completion; exceptional settlement is excluded where stated.',sourceEvidenceUnchanged:true,sources:engine.research.sources,uncertainty:result.uncertainty,calibratedProbability:null,hypothetical:true,actualWagerRecorded:false};
 }
 if(result.hypothetical?.kind!=='availability_what_if'||stableHash(result.hypothetical.assumptions)!==stableHash(input.whatIf))throw new ApiError('The worker did not confirm the exact requested hypothetical assumption.',502);
 const comparisons=input.selections.map((row:any)=>{const outcome=result.contracts.find((item:any)=>item.id===row.contract.id),p=row.side==='YES'?outcome.probability:outcome.noProbability??1-outcome.probability-outcome.pushProbability;return{researchId:row.researchId,contractId:row.contract.id,side:row.side,baselineProbability:row.baselineProbability,modifiedProbability:p,delta:p-row.baselineProbability};});
 return{kind:'what_if',game:input.game,simulations:result.simulations,modelVersion:result.modelVersion,assumptions:input.whatIf,baseline:input.baseline,modified:{homeWinProbability:result.homeWinProbability,awayWinProbability:result.awayWinProbability,tieProbability:result.tieProbability,players:result.players},delta:{homeWinProbability:result.homeWinProbability-input.baseline.homeWinProbability,awayWinProbability:result.awayWinProbability-input.baseline.awayWinProbability,contracts:comparisons},sourceEvidenceUnchanged:true,sources:engine.research.sources,uncertainty:result.uncertainty,calibratedProbability:null,hypothetical:true,currentVerifiedConditionsChanged:false,actualWagerRecorded:false,limitations:['This is a user-selected historical availability cohort, not a confirmed injury update or a causal injury estimate.','No arbitrary pace, snap-share, pass-rate, weather or efficiency multipliers were applied.','Sampling error and whole-game bootstrap sensitivity remain separate from unmeasured structural and future-availability uncertainty.']};
}

export async function executePrivatePropResearch(ctx:CloudContext,id:string){
 requireCloudUser(ctx);const stored=await record(ctx,id,KIND),original=stored.data as Job;verifyInput(ctx,id,original);if(original.status!=='queued')return;
 const lease=randomUUID(),job:Job={...original,status:'running',lease,updatedAt:new Date().toISOString(),error:null};if(!await cas(ctx,id,'queued',job))return;
 let quotaClaimed=false;
 try{
  const quota=await sharedWrite({action:'job_claim',id:job.input.quotaId,lease});
  if(!quota)throw new ApiError('Research compute capacity is temporarily unavailable. Your private inputs remain saved; no probabilities were invented.',429);quotaClaimed=true;
  const endpoint=process.env.SIMULATION_SERVICE_URL,secret=process.env.SIMULATION_SERVICE_TOKEN;if(!endpoint||!secret||secret.length<32)throw new ApiError('The private research worker is unavailable.',503);
  const url=new URL('public/analyze',endpoint.endsWith('/')?endpoint:endpoint+'/'),input=job.input;
  const response=await fetch(url,{method:'POST',headers:{Authorization:`Bearer ${secret}`,'Content-Type':'application/json'},body:JSON.stringify({game:input.game,simulations:input.simulations,seed:2026,inputContext:{...input.context,contractDefinitions:input.contractDefinitions,...input.selectedOutcomes?{selectedOutcomes:input.selectedOutcomes}:{},...input.whatIf?{whatIf:input.whatIf}:{}}}),signal:AbortSignal.timeout(245000),cache:'no-store'});
  if(!response.ok){let message='The private full-game research engine could not complete this request.';if(response.status===422)try{const value=await response.json();message=String(value.detail??value.error??message).slice(0,1000);}catch{}throw new ApiError(message,response.status===422?422:502);}
  const result=finiteJson(checkedEngine(input,await response.json())),complete:Job={...job,status:'completed',result,resultProof:attestCloudResult(ctx,id,result),updatedAt:new Date().toISOString(),error:null};
  if(!await cas(ctx,id,'running',complete,lease))throw new ApiError('The private worker lease changed. This response was not published.',409);
  // Only neutral accounting metadata enters public shared jobs/snapshots.
  await sharedWrite({action:'job_complete',id:input.quotaId,lease,result:{purpose:'private_research',simulations:input.simulations}}).catch(()=>{});
 }catch(error){
  const failed:Job={...job,status:'failed',result:null,error:error instanceof ApiError?error.message:'Private research was interrupted. Your signed inputs remain saved.',errorStatus:error instanceof ApiError?error.status:503,updatedAt:new Date().toISOString()};
  await cas(ctx,id,'running',failed,lease).catch(()=>{});
  if(quotaClaimed)await sharedWrite({action:'job_fail',id:job.input.quotaId,lease,error:'Private research did not complete. Private inputs and diagnostics are not published.'}).catch(()=>{});
 }
}

export async function readPrivatePropResearch(ctx:CloudContext,id:string){
 requireCloudUser(ctx);if(!/^[a-f0-9-]{36}$/i.test(id))throw new ApiError('Choose a valid private research record.',422);
 let job=(await record(ctx,id,KIND)).data as Job;verifyInput(ctx,id,job);
 if(job.status==='running'&&Date.now()-Date.parse(job.updatedAt)>6*60000){const queued={...job,status:'queued',lease:null,updatedAt:new Date().toISOString(),error:'The previous worker lease expired. Signed inputs remain available for retry.'};if(await cas(ctx,id,'running',queued,job.lease))job=queued;else job=(await record(ctx,id,KIND)).data as Job;}
 if(job.status==='queued')after(async()=>{await executePrivatePropResearch(ctx,id).catch(()=>{});});
 return safeOutput(ctx,id,job);
}

/** Browsing saved research never dispatches a batch of expensive simulations. */
export async function listPrivatePropResearch(ctx:CloudContext,kind:ResearchKind){
 requireCloudUser(ctx);if(!['combination','what_if'].includes(kind))throw new ApiError('Choose combination or what-if history.',422);
 const rows=await records(ctx,KIND,{dataKind:kind,limit:20});
 return rows.map(row=>{
  const job=row.data as Job;let status=job.status,error=job.error??null,provenanceVerified=false;
  try{verifyInput(ctx,row.id,job);if(job.status==='completed'){verifyCloudResult(ctx,row.id,job);provenanceVerified=true;}}
  catch{status='provenance_unverified';error='Saved provenance could not be verified. The original private record remains available in your account export.';}
  return{id:row.id,kind,status,game:job.input?.game??null,createdAt:job.createdAt??row.created_at,updatedAt:job.updatedAt??row.updated_at,error,provenanceVerified,hypothetical:true,actualWagerRecorded:false};
 });
}
