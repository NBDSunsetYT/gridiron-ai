import {after} from 'next/server';
import {createHash,randomUUID} from 'node:crypto';
import {cloudClient} from '../cloud/context';
import {ApiError} from '../auth';
import {canonicalJson} from '../cloud/attestation';
import {saveSharedResearch} from '../storage/research';
import {readResearchObject,isResearchPointer} from '../public-nfl/objects';
import {compareFreeProp} from '../free-prop-comparison';
import {wilson} from '../model';
import {probabilityCapacity} from './capacity';
import {hierarchicalThreshold} from '../props/distribution';
type Sport='NFL'|'CFB';
const VERSION='automatic-props-12.1.0',JOB_NAMESPACE='automatic-props-12.0.0';
const hash=(v:unknown)=>createHash('sha256').update(canonicalJson(v)).digest('hex');
const jobId=(sport:Sport,event:string)=>hash([JOB_NAMESPACE,sport,event]);
export async function autoOperation(payload:Record<string,any>):Promise<any>{
 const token=process.env.GRIDIRON_PUBLIC_INGEST_TOKEN;if(!token)throw new ApiError('Automatic research storage is not configured.',503);
 const {data,error}=await cloudClient().rpc('gridiron_auto_props',{token,payload});if(error)throw new ApiError('Automatic research queue is temporarily unavailable. Saved evidence remains intact.',503);return data;
}
export function automaticInput(sport:Sport,row:any,injuries:any[]){return hash([VERSION,sport,row.espnEventId,row.kickoff,injuries.map(i=>({id:i.player_id,status:i.status_code,restriction:i.snap_restriction??null})).sort((a,b)=>String(a.id).localeCompare(String(b.id)))]);}
export function empiricalComparison(row:any,evidence:any,playerId:string|null){
 const d=playerId?evidence.players?.[playerId]?.[row.statistic]:null;
 if(!d)return null;
 if(!['Over','Under'].includes(row.side)||row.threshold===null||row.threshold===undefined||String(row.threshold).trim()===''||!Number.isFinite(Number(row.threshold))||row.period&&!['full','full_game','game'].includes(row.period))return{modelProbability:null,reasonCode:row.period?'market_period_unsupported':'exact_definition_unsupported',reason:row.period?'The source defines a partial-game market; full-game observations cannot establish that outcome.':'An exact numeric threshold and supported Over/Under predicate are required. No event-contract or touchdown settlement rule was inferred.'};
 const bins=d.histogram,n=d.sampleSize;if(!Number.isSafeInteger(n)||n<1||n>64||!Array.isArray(bins)||bins.some((b:any)=>!Number.isFinite(b.value)||!Number.isSafeInteger(b.count)||b.count<0)||bins.reduce((a:number,b:any)=>a+b.count,0)!==n)return null;
 const hierarchical=hierarchicalThreshold(d,Number(row.threshold),row.side,row.sport,row.statistic);if(hierarchical)return hierarchical;
 const hits=bins.filter((b:any)=>row.side==='Over'?b.value>Number(row.threshold):b.value<Number(row.threshold)).reduce((a:number,b:any)=>a+b.count,0);
 return{modelProbability:null,rawProbability:null,empiricalProbability:hits/n,estimateProbability:hits/n,method:'empirical_history',methodLabel:'Historical participation-conditioned estimate',historicalHits:hits,historicalSampleSize:n,historicalInterval95:wilson(hits,n),simulations:null,successfulSimulations:null,monteCarloInterval95:null,monteCarloStandardError:null,calibratedProbability:null,expectedValue:null,state:'ready',reasonCode:null,modelUncertainty:null,reason:evidence.limitations?.join(' ')??'Historical player-game frequency; matchup and participation uncertainty are not fully quantified.'};
}
export function attachAutomaticEvidence(row:any,evidence:any,job:any,injuries:any[]){
 const marketImpliedProbability=row.marketCurrent===false?null:row.americanOdds<0?Math.abs(row.americanOdds)/(100+Math.abs(row.americanOdds)):100/(100+row.americanOdds);
 const base={...row,modelProbability:null,rawProbability:null,empiricalProbability:null,estimateProbability:null,calibratedProbability:null,expectedValue:null,simulations:null,marketImpliedProbability,method:null,state:'calculating_probability',reason:job?.reason??'Research is being calculated automatically on the server.',researchJobId:job?.id??null,retryAt:job?.due_at??null,modelUncertainty:null};
 if(Date.parse(row.kickoff)<=Date.now())return{...base,state:'source_unavailable',reasonCode:'pregame_only',reason:'Kickoff has passed. A verified live player model is unavailable.'};
 if(!row.espnEventId||!/^espn:\d+$/.test(row.player?.id??''))return{...base,state:'source_unavailable',reasonCode:'identity_crosswalk_unavailable',reason:'A verified event/player identity crosswalk is unavailable. No name-only match was made.'};
 if(!evidence)return{...base,state:job?.status==='delayed'?'data_delayed':base.state};
 if(evidence.sport!==row.sport||evidence.espnEventId!==row.espnEventId||Date.parse(evidence.eventStart)!==Date.parse(row.kickoff))return{...base,state:'source_unavailable',reasonCode:'evidence_identity_mismatch',reason:'Stored research does not match the exact sport, event and kickoff.'};
 const secondary=evidence.secondaryEvidence;
 const match=(p:any)=>row.sport==='CFB'?p.id==='cfb:'+row.player.id:'espn:'+p.espnId===row.player.id;
 const primary=(evidence.playerCatalog??evidence.research?.playerCatalog??[]).filter(match),extra=(secondary?.playerCatalog??[]).filter(match);
 const ambiguous=primary.length>1||extra.length>1||primary.length===1&&extra.length===1&&primary[0].id!==extra[0].id,pid=ambiguous?null:primary[0]?.id??extra[0]?.id??null;
 const injury=injuries.find((i:any)=>i.player_id===row.player.id),restricted=injury&&!['active','cleared'].includes(String(injury.status_code??'').toLowerCase());
 if(restricted||pid&&(evidence.withheldPlayers?.[pid]||secondary?.withheldPlayers?.[pid]||evidence.result?.publicPlayerForecastsWithheld?.[pid]))return{...base,state:'source_unavailable',injuryStatus:injury?.status??null,reasonCode:'availability_mixture_unfitted',reason:evidence.withheldPlayers?.[pid!]??secondary?.withheldPlayers?.[pid!]??evidence.result?.publicPlayerForecastsWithheld?.[pid!]??'Verified availability is restricted or uncertain. No calibrated availability mixture supports this player.'};
 const r=evidence.result,d=pid?r?.players?.[pid]?.[row.statistic]:null;
 let comparison:any=evidence.method==='empirical_history'?empiricalComparison(row,evidence,pid):compareFreeProp(row,d?{sport:row.sport,providerPlayerId:row.player.id,providerEventId:row.eventId,kickoff:evidence.eventStart,stale:false,simulations:r.simulations,statistic:row.statistic,histogram:d.histogram,modelVersion:r.modelVersion}:null);
 let usedEvidence=evidence;
 if((!comparison||comparison.modelProbability===null&&comparison.method!=='empirical_history')&&secondary){const fallback=empiricalComparison(row,secondary,pid);if(fallback){comparison=fallback;usedEvidence=secondary;}}
 if(!comparison||comparison.modelProbability===null&&comparison.method!=='empirical_history')return{...base,state:'source_unavailable',reasonCode:comparison?.reasonCode??'historical_sample_insufficient',reason:comparison?.reason??'No verified current- or previous-season distribution supports this exact player/statistic, or the market definition is incompatible. See source and coverage details.'};
 if(usedEvidence.method!=='empirical_history')comparison={...comparison,rawProbability:comparison.modelProbability,estimateProbability:comparison.modelProbability,method:'full_game_simulation',methodLabel:'Complete-game simulation · raw',state:'ready',monteCarloStandardError:Math.sqrt(comparison.modelProbability*(1-comparison.modelProbability)/r.simulations)};
 const stale=evidence.triggerHash!==job.input_hash||Date.parse(job.due_at)<=Date.now()||job.status!=='ready'||Date.now()-Date.parse(job.updated_at??evidence.checkedAt)>16*60000;
 return{...base,...comparison,stale,state:stale?'data_delayed':'ready',reason:comparison.reason,modelGameId:evidence.gameId,modelPlayerId:pid,modelVersion:comparison.modelVersion??usedEvidence.modelVersion??r?.modelVersion,inputVersion:usedEvidence.inputVersion,simulationId:evidence.analysisId??null,probabilityDistribution:usedEvidence.method==='empirical_history'?usedEvidence.players[pid!][row.statistic].histogram:d?.histogram,modelDataVersion:r?.inputDataVersion??null,modelFeatureVersion:r?.baseFeatureVersion??r?.inputFeatureVersion??null,evidenceCutoff:r?.evidenceCutoff??null,simulationCreatedAt:r?.createdAt??null,calculatedAt:usedEvidence.calculatedAt??r?.createdAt,checkedAt:job.updated_at??evidence.checkedAt,researchSources:usedEvidence.sources??evidence.research?.sources??[],researchAssumptions:usedEvidence.research?.injuryImpact??evidence.research?.injuryImpact??usedEvidence.featureCoverage??null,playerUsage:usedEvidence.playerUsage?.[pid!]??null,researchPersistence:{saved:true,kind:'immutable_shared_research'},fallbackReason:evidence.fallbackReason??null};
}
async function evidenceFor(job:any){
 const sport=job.sport as Sport,event=job.event_id,capacity=await probabilityCapacity().catch(()=>null),allowCompute=Boolean(capacity&&capacity.used+10000<=capacity.backgroundLimit);
 let game:any,state:any,simulationFailure:string|undefined,unstartedGameIds:string[]=[];
 if(sport==='CFB'){
  const c=await import('../college-football/service');let detail=await c.collegeGameDetail('cfb:espn:'+event);game=detail.game;
  if(!detail.analysis&&allowCompute&&detail.canAnalyze){try{detail=await c.analyzeCollegeGame(game.id,10000);}catch(e){simulationFailure=e instanceof Error?e.message:'Complete-game simulation unavailable';}}
  if(detail.analysis&&!detail.analysis.stale)state={result:detail.analysis.result,research:detail.analysis.research,analysisId:detail.analysis.id,inputVersion:detail.analysis.inputVersion};
 }else{
  const c=await import('../public-nfl/service');const schedule=await c.loadSchedule();game=schedule.games.find(g=>String(g.espnId)===event);unstartedGameIds=schedule.games.filter(g=>Date.parse(g.startTime)>Date.now()).map(g=>g.id).slice(0,128);if(!game)throw new ApiError('The provider event is absent from the verified NFL schedule.',422);
  const [saved,prepared]=await Promise.allSettled([(await import('../sportsbook-reference/service')).existingModel(game),c.verifiedProbabilityInputs(game.id,10000)]);const old=saved.status==='fulfilled'?saved.value:null,verified=prepared.status==='fulfilled'?prepared.value:null;if(old?.result?.result&&verified&&old.input_hash===verified.inputHash)state={result:old.result.result,research:old.result.research,analysisId:old.id,inputVersion:old.input_hash};
  if(!state&&allowCompute){try{const b=await(await import('./nfl-baseline')).nflProbabilityBaseline(game.id,10000);state={...b,analysisId:b.id};}catch(e){simulationFailure=e instanceof Error?e.message:'Complete-game simulation unavailable';}}
 }
 if(!game||game.status!=='scheduled'||Date.parse(game.startTime)<=Date.now()||Date.parse(job.kickoff)!==Date.parse(game.startTime))throw new ApiError('The verified schedule no longer supports this exact future kickoff.',422);
 const envelope={format:VERSION,sport,gameId:game.id,espnEventId:event,eventStart:game.startTime,triggerHash:job.input_hash,checkedAt:new Date().toISOString()};
 const full=state?.result?.simulations>=10000?{...envelope,...state,method:'full_game_simulation'}:null;
 const endpoint=process.env.SIMULATION_SERVICE_URL,token=process.env.SIMULATION_SERVICE_TOKEN;if(!endpoint||!token){if(full)return full;throw new ApiError('The private historical-statistics worker is unavailable.',503);}
 const payload=sport==='NFL'?{unstartedGameIds,game:{id:game.id,home:game.home.id,away:game.away.id,startTime:game.startTime,season:game.season,week:game.week}}:{game:(await import('../college-football/service')).gamePayload(game)};
 let response:Response;try{response=await fetch(new URL(sport==='NFL'?'public/prop-history':'cfb/public/prop-history',endpoint.endsWith('/')?endpoint:endpoint+'/'),{method:'POST',headers:{Authorization:'Bearer '+token,'Content-Type':'application/json'},body:JSON.stringify(payload),cache:'no-store',signal:AbortSignal.timeout(180000)});}catch(error){if(full)return{...full,secondaryEvidenceStatus:'source_delayed'};throw error;}const value=await response.json().catch(()=>null);
 if(!response.ok||value?.sport!==sport||value.gameId!==game.id||!value.players||Date.parse(value.eventStart)!==Date.parse(game.startTime)){if(full)return{...full,secondaryEvidenceStatus:'unavailable'};throw new ApiError(typeof value?.detail?.message==='string'?value.detail.message:typeof value?.detail==='string'?value.detail:'Verified historical player-game evidence is unavailable.',503);}
 if(full)return{...full,secondaryEvidence:value};
 return{...value,...envelope,fallbackReason:simulationFailure??(!allowCompute?'Background complete-game capacity is reserved or exhausted. No limit was increased.':'No current complete-game distribution exists.')};
}
let running:Promise<void>|null=null;
export async function drainAutomaticProps(maxGames=2){
 if(running)return running;const task=(async()=>{const began=Date.now();for(let i=0;i<maxGames&&Date.now()-began<60000;i++){
  const lease=randomUUID(),job=await autoOperation({action:'claim',lease});if(!job)return;
  try{const value=await evidenceFor(job),identity=(v:any)=>hash([v.method,v.inputVersion,v.modelVersion??v.result?.modelVersion,v.secondaryEvidence?.inputVersion??null]),evidenceHash=identity(value);let ref;if(isResearchPointer(job.result_ref)){try{const previous=await readResearchObject(job.result_ref);if(identity(previous)===evidenceHash&&previous.triggerHash===value.triggerHash)ref=job.result_ref;}catch{/* New verified evidence can repair an unreadable current reference; old versions remain. */}}ref??=await saveSharedResearch(job.sport,value.gameId,value.method==='full_game_simulation'?'simulation':'matchup_report',value);await autoOperation({action:'finish',id:job.id,lease,inputHash:job.input_hash,evidenceHash,resultRef:ref});}
  catch(error){await autoOperation({action:'finish',id:job.id,lease,inputHash:job.input_hash,reason:error instanceof Error?error.message:'Research source temporarily unavailable.'});}
 }})();running=task;try{await task;}finally{running=null;}
}
const objectCache=new Map<string,{until:number;value:any}>();
export async function automaticPropResearch(sport:Sport,board:any){
 const candidates=board.items.filter((r:any)=>/^\d+$/.test(r.espnEventId??'')&&Date.parse(r.kickoff)>Date.now()).sort((a:any,b:any)=>Date.parse(a.kickoff)-Date.parse(b.kickoff));
 const unique=[...new Map<string,any>(candidates.map((r:any)=>[r.espnEventId,r])).values()].slice(0,20),injuries=board.injuries??[];
 const jobs=unique.map(r=>({id:jobId(sport,r.espnEventId),sport,eventId:r.espnEventId,kickoff:r.kickoff,inputHash:automaticInput(sport,r,injuries)}));
 if(!jobs.length)return{...board,items:board.items.map((r:any)=>attachAutomaticEvidence(r,null,null,injuries)),automatic:true,analysisComplete:false};
 await autoOperation({action:'enqueue',jobs});const stored=await autoOperation({action:'read',ids:jobs.map(j=>j.id)}),evidence=new Map<string,any>();
 await Promise.all(stored.map(async(j:any)=>{if(!isResearchPointer(j.result_ref))return;try{const id=j.result_ref._sharedResearchObject.id,cached=objectCache.get(id),value=cached&&cached.until>Date.now()?cached.value:await readResearchObject(j.result_ref);if(objectCache.size>=20)objectCache.delete(objectCache.keys().next().value!);objectCache.set(id,{until:Date.now()+30000,value});evidence.set(j.id,value);}catch{/* Immutable reference remains intact; automatic retry continues. */}}));
 after(async()=>{await drainAutomaticProps().catch(()=>{});});
 const items=board.items.map((r:any)=>{const id=jobId(sport,r.espnEventId),j=stored.find((j:any)=>j.id===id);return attachAutomaticEvidence(r,evidence.get(id),j,injuries);});
 after(async()=>{await Promise.allSettled(stored.map(async(j:any)=>{
  const estimates=items.filter((r:any)=>r.researchJobId===j.id&&r.state==='ready'&&!r.stale).map((r:any)=>({sport,eventId:r.eventId,gameId:r.modelGameId,playerId:r.player.id,modelPlayerId:r.modelPlayerId,market:r.market,statistic:r.statistic,threshold:r.threshold,side:r.side,method:r.method,rawProbability:r.rawProbability,empiricalProbability:r.empiricalProbability,posteriorProbability:r.posteriorProbability??null,estimateProbability:r.estimateProbability??null,calibratedProbability:r.calibratedProbability,simulations:r.simulations,hits:r.successfulSimulations??r.historicalHits,sampleSize:r.historicalSampleSize??null,interval95:r.calibratedInterval95??r.modelInterval95??r.monteCarloInterval95??r.historicalInterval95,priorEffectiveSampleSize:r.priorEffectiveSampleSize??null,distributionArtifactId:r.distributionArtifactId??null,modelVersion:r.modelVersion,inputVersion:r.inputVersion,calculatedAt:r.calculatedAt,sourceQuote:{provider:r.provider,book:r.book.key,americanOdds:r.americanOdds,observedAt:r.sourceUpdatedAt,current:r.marketCurrent!==false},assumptions:r.reason}));
  if(!estimates.length)return;const evidenceHash='selections:'+hash(estimates.map(({sourceQuote,...estimate}:any)=>({...estimate,sourceQuote:Object.fromEntries(Object.entries(sourceQuote).filter(([key])=>key!=='observedAt'))}))),snapshot={format:'automatic-prop-predictions-v12',sport,gameId:estimates[0].gameId,estimates};
  const check=await autoOperation({action:'snapshot',id:j.id,inputHash:j.input_hash,evidenceHash});if(!check?.needsObject)return;
  const ref=await saveSharedResearch(sport,snapshot.gameId,'matchup_report',snapshot);await autoOperation({action:'snapshot',id:j.id,inputHash:j.input_hash,evidenceHash,resultRef:ref});
 }));});
 return{...board,items,automatic:true,analysisScope:'Automatic matchup batches. Prices never determine model distributions. Empirical estimates remain distinct from complete-game simulations.',analysisComplete:items.every((r:any)=>r.state==='ready'||r.state==='source_unavailable'),researchQueue:{queued:stored.filter((j:any)=>['queued','running'].includes(j.status)).length,delayed:stored.filter((j:any)=>j.status==='delayed').length},persistence:{saved:true,status:'shared_immutable_research',message:'Completed distributions and versions are saved automatically; private personal records are unchanged.'}};
}
