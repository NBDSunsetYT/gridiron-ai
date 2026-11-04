import {randomUUID} from 'node:crypto';
import {after} from 'next/server';
import {computeAllowed,deferWorker,assertComputeAllowed} from '../compute/policy';
import {enqueueCompute} from '../compute/queue';
import performance from '../../docs/reports/v4-model-benchmark.json';
import {ApiError} from '../auth';
import {createAiProviderClient} from '../ai-provider';
import {fetchPublicSchedule,fetchInjuries,fetchWeather,fetchStatisticsVersion,nflSeason,sha} from './sources';
import {fetchPublicMarkets,valuePublicMarkets} from './markets';
import {sharedCache,putCache,fresh,latestJob,latestJobs,cachedContextStates,sharedWrite,type SharedJob} from './store';
import type {PublicGame,PublicDashboard,PublicGameDetail,PublicAnalysis,PublicAnalysisSummary,PublicSummary,ResearchSource,PublicCoverage,PublicInjury,PublicWeather} from './types';

export const PUBLIC_PIPELINE_VERSION='public-nfl-7.0.0';
const SCHEDULE_TTL=15*60000,CONTEXT_TTL=10*60000,FAILED_CONTEXT_TTL=60000,ANALYSIS_TTL=60*60000;
type Schedule={games:PublicGame[];sources:ResearchSource[];updatedAt:string;inputVersion:string};
type Context={injuries:PublicCoverage<PublicInjury>;weather:PublicWeather;markets:PublicCoverage<Record<string,any>>;statisticsVersion:string;statisticsSources?:ResearchSource[];sources:ResearchSource[];updatedAt:string;pipelineVersion?:string;inputVerified?:boolean;verificationMessage?:string};
const STATISTIC_SOURCE_IDS=['nflverse-pbp','nflverse-injuries','nflverse-snaps','nflverse-rosters','nflverse-depth','nflverse-player-stats','nflverse-team-stats'];
export function contextInputsVerified(context:Context):boolean{
 if(context.inputVerified===false||context.pipelineVersion!==PUBLIC_PIPELINE_VERSION||!context.injuries||!['available','partial'].includes(context.injuries.status))return false;
 const candidates=context.statisticsSources===undefined?context.sources:context.statisticsSources;if(!Array.isArray(candidates))return false;
 const sources=candidates.filter(source=>source&&STATISTIC_SOURCE_IDS.includes(source.id));
 return STATISTIC_SOURCE_IDS.every(id=>sources.some(source=>source.id===id&&source.status==='available'))&&sources.every(source=>source.status==='available');
}
function recentVerifiedContext(context:Context){const age=Date.now()-Date.parse(context.updatedAt);return contextInputsVerified(context)&&Number.isFinite(age)&&age>=-60000&&age<=3*CONTEXT_TTL;}
let scheduleMemory:Schedule|undefined;
let schedulePending:Promise<Schedule>|undefined;
const contextPending=new Map<string,Promise<Context>>();
const safeRead=async<T>(read:()=>Promise<T>,fallback:T):Promise<T>=>{try{return await read();}catch{return fallback;}};

export async function loadSchedule(force=false):Promise<Schedule>{
 if(!force&&scheduleMemory&&Date.now()-Date.parse(scheduleMemory.updatedAt)<SCHEDULE_TTL)return scheduleMemory;
 const cache=await safeRead(()=>sharedCache('schedule',String(nflSeason())),null);
 if(!force&&fresh(cache)){scheduleMemory=cache!.data as Schedule;return scheduleMemory;}
 if(!force&&scheduleMemory&&Date.now()-Date.parse(scheduleMemory.updatedAt)<SCHEDULE_TTL)return scheduleMemory;
 if(schedulePending)return schedulePending;
 schedulePending=(async()=>{try{const result=await fetchPublicSchedule();scheduleMemory=result;await putCache('schedule',String(nflSeason()),result,result.inputVersion,SCHEDULE_TTL).catch(()=>{});return result;}catch(error){if(cache?.data?.games?.length)return cache.data as Schedule;if(scheduleMemory)return scheduleMemory;throw error;}finally{schedulePending=undefined;}})();
 return schedulePending;
}
function clockStatus(game:PublicGame,now=Date.now()):PublicGame{return game.status==='scheduled'&&Date.parse(game.startTime)<=now?{...game,statusMessage:'Scheduled kickoff has passed; a live score has not been verified.'}:game;}
export function currentDashboardGames(games:PublicGame[],now=Date.now()){return games.filter(g=>Date.parse(g.startTime)>=now-2*86400000&&Date.parse(g.startTime)<=now+28*86400000).slice(0,64).map(g=>clockStatus(g,now));}
export async function trustedGame(id:string){if(!/^\d{4}_\d{2,3}_[A-Z0-9]{2,3}_[A-Z0-9]{2,3}$/.test(id))throw new ApiError('NFL game not found.',404);const game=(await loadSchedule()).games.find(g=>g.id===id);if(!game)throw new ApiError('This game is not present in the verified NFL schedule.',404);return clockStatus(game);}
export function evidenceHash(game:PublicGame,ctx:Context,count=10000){
 // Current weather remains in verified context, citations and explanations.
 // This engine has no fitted numerical weather adjustment. A new forecast's
 // collection time or wind reading cannot change the simulated distribution,
 // so it must not generate another 10,000 games and duplicate predictions.
 // Introduce a versioned, validated adjustment here when such a model exists.
 return sha({game:{id:game.id,home:game.home.id,away:game.away.id,startTime:game.startTime,season:game.season,week:game.week},simulations:count,engine:PUBLIC_PIPELINE_VERSION,statisticsVersion:ctx.statisticsVersion,injuries:ctx.injuries.items.map(i=>({id:i.id,status:i.status,practice:i.practiceParticipation})).sort((a,b)=>a.id.localeCompare(b.id)),weatherAdjustmentVersion:null,markets:ctx.markets.items.filter(item=>item.definition?.kind!=='game_winner').map(item=>({id:item.id??item.contractId,definition:item.definition??item.settlement??null,rules:item.rules??item.settlementRule??null})).sort((a,b)=>String(a.id).localeCompare(String(b.id)))});
}
export async function gameContext(game:PublicGame,force=false):Promise<Context>{
 const cache=await safeRead(()=>sharedCache('detail',game.id),null);if(!force&&fresh(cache)&&cache!.data.pipelineVersion===PUBLIC_PIPELINE_VERSION){const previous=cache!.data as Context,verified=contextInputsVerified(previous);if(verified||Date.now()-Date.parse(cache!.updated_at??previous.updatedAt)<FAILED_CONTEXT_TTL)return{...previous,inputVerified:verified};}
 if(contextPending.has(game.id))return contextPending.get(game.id)!;
 const task=(async()=>{try{
  const [injuries,weather,statistics,markets]=await Promise.all([fetchInjuries(game),fetchWeather(game),fetchStatisticsVersion(game),fetchPublicMarkets(game)]);
  const checkedAt=new Date().toISOString();
  const statisticSources=statistics.sources??[statistics.source];
  const context:Context={injuries,weather,markets,statisticsVersion:statistics.version,statisticsSources:statisticSources,sources:[...game.sources,...injuries.sources,...weather.sources,...statisticSources,...markets.sources],updatedAt:checkedAt,pipelineVersion:PUBLIC_PIPELINE_VERSION};
  context.inputVerified=contextInputsVerified(context);if(!context.inputVerified)context.verificationMessage='Current statistical or injury source verification is unavailable. Missing reports are not evidence of healthy players.';
  await putCache('detail',game.id,context,evidenceHash(game,context),context.inputVerified?CONTEXT_TTL:FAILED_CONTEXT_TTL).catch(()=>{});return context;
 }catch(error){if(cache?.data){const previous=cache.data as Context,fallback={...previous,inputVerified:false,verificationMessage:'Latest source verification failed; prior evidence is historical.',injuries:{...previous.injuries,status:'unavailable' as const,message:'The latest injury/statistical source verification failed. Prior report entries remain historical; no current availability is assumed.'}};await putCache('detail',game.id,fallback,evidenceHash(game,fallback),FAILED_CONTEXT_TTL).catch(()=>{});return fallback;}throw error;}finally{contextPending.delete(game.id);}})();
 contextPending.set(game.id,task);return task;
}
async function currentContext(game:PublicGame):Promise<Context>{
 const context=await gameContext(game),markets=await fetchPublicMarkets(game);
 return{...context,markets,sources:[...context.sources.filter(s=>!s.id.startsWith('kalshi-')),...markets.sources]};
}
function briefHash(jobId:string|null,inputHash:string|null|undefined,context:Context){return sha({jobId,inputHash,markets:context.markets.items.map(item=>({id:item.id,yesAskCents:item.yesAskCents,yesBidCents:item.yesBidCents,definition:item.definition,fees:item.fees})),marketStatus:context.markets.status});}
export function analysisSummary(job:SharedJob,stale=false):PublicAnalysisSummary{
 const output=job.result?.result??job.result;
 const transient=job.status==='failed'&&job.error?.startsWith('Research is busy');
 return{id:job.id,status:stale?'stale':transient?'queued':job.status,simulations:Number(output?.simulations??job.data.simulations??10000),updatedAt:job.updated_at,stale,error:job.error,...typeof output?.homeWinProbability==='number'?{homeWinProbability:output.homeWinProbability,awayWinProbability:output.awayWinProbability,tieProbability:output.tieProbability}:{},modelVersion:output?.modelVersion,inputHash:job.input_hash};
}
function publicAnalysis(job:SharedJob,game:PublicGame,context:Context,requiredInputHash:string|null):PublicAnalysis{
 const verified=recentVerifiedContext(context),stale=!verified||!requiredInputHash||job.input_hash!==requiredInputHash||Date.parse(game.startTime)<=Date.now(),wrapper=job.result;
 return{...analysisSummary(job,stale),currentInputHash:requiredInputHash,requiredInputHash,inputsVerified:verified,gameId:game.id,createdAt:job.created_at,result:wrapper?.result??null,research:wrapper?.research??null,summary:wrapper?.summary??null,sourceUpdatedAt:context.updatedAt,injuryCheckedAt:context.injuries.checkedAt,weatherCheckedAt:context.weather.checkedAt,marketCheckedAt:context.markets.checkedAt,dataQuality:{injuries:context.injuries.status,weather:context.weather.status,markets:context.markets.status,inputsVerified:verified,model:'research_only',missingDataNotAssumed:true}};
}
export async function publicDashboard():Promise<PublicDashboard>{
 const schedule=await loadSchedule(),available=currentDashboardGames(schedule.games),states=await safeRead(()=>cachedContextStates(available.map(game=>game.id)),new Map());
 const required=new Map<string,string>();for(const game of available){const context=states.get(game.id)?.data as Context|undefined;if(context&&recentVerifiedContext(context))required.set(game.id,evidenceHash(game,context));}
 const matching=required.size?await safeRead(()=>latestJobs(100,[...required.values()]),[]):[],byHash=new Map(matching.map(job=>[job.input_hash,job]));
 const games=available.map(game=>{const hash=required.get(game.id)??null,job=hash?byHash.get(hash):null,verified=hash!==null,stale=!verified||Date.parse(game.startTime)<=Date.now()||job?.input_hash!==hash;return{...game,analysis:job?{...analysisSummary(job,stale),requiredInputHash:hash,currentInputHash:hash,inputsVerified:verified}:null};});
 const metrics=(performance as any).metrics.ensemble,market=(performance as any).marketComparison;
 return{games,updatedAt:schedule.updatedAt,sources:schedule.sources,guestAccess:true,refresh:{status:Date.now()-Date.parse(schedule.updatedAt)<SCHEDULE_TTL?'fresh':'refreshing',message:'Published NFL schedules refresh automatically. Research results retain their source and calculation times.'},modelPerformance:{n:performance.n,brier:metrics.brier,logLoss:metrics.logLoss,calibration:metrics.calibration,marketBrier:market?.marketOnCommonGames?.brier??null,version:performance.version,updatedAt:performance.createdAt,productionEligible:false,message:'Separate historical home-win benchmark; these results do not validate the automatic play-by-play simulator or player distributions. Historical publication times are unverified; no profitable edge is established.'}};
}
export async function publicGameDetail(id:string,simulations=10000):Promise<PublicGameDetail>{
 const game=await trustedGame(id),context=await currentContext(game),verified=recentVerifiedContext(context),requiredInputHash=verified?evidenceHash(game,context,simulations):null,matching=requiredInputHash?await safeRead(()=>latestJob(id,requiredInputHash),null):null,job=matching??await safeRead(()=>latestJob(id),null),analysis=job?publicAnalysis(job,game,context,requiredInputHash):null;
 context.markets=valuePublicMarkets(context.markets,analysis?.result);
 if(analysis&&(analysis.stale||analysis.summary?.generatedByAI!==true))analysis.summary=evidenceBrief(game,context,analysis.stale?null:analysis.result,analysis.research);
 const savedSummary=job?await safeRead(()=>sharedCache('summary',id),null):null;
 if(analysis&&!analysis.stale&&savedSummary?.input_hash===briefHash(job?.id??null,job?.input_hash,context)&&fresh(savedSummary))analysis.summary=savedSummary!.data.summary;
 if(job&&!analysis?.stale&&(job.status==='queued'||job.status==='running'&&Date.now()-Date.parse(job.updated_at)>6*60000||job.status==='failed'&&job.error?.startsWith('Research is busy')&&Date.now()-Date.parse(job.updated_at)>2*60000))scheduleJob(job.id);
 return{game:{...game,analysis:analysis?{...analysisSummary(job!,analysis.stale),requiredInputHash,currentInputHash:requiredInputHash,inputsVerified:verified}:null},analysis,status:analysis?.status==='completed'?'ready':analysis?.status??'unavailable',requiredInputHash,currentInputHash:requiredInputHash,inputsVerified:verified,sources:context.sources,injuries:context.injuries,weather:context.weather,markets:context.markets,statistics:analysis?.research??null,summary:analysis?.summary??null,ai:{available:Boolean(process.env.OPENAI_API_KEY),generatedByAI:Boolean(analysis?.summary?.generatedByAI)},updatedAt:context.updatedAt,message:!verified?'Current statistical or injury source verification is unavailable. Prior snapshots remain historical; new simulations will wait for verified inputs.':analysis?'Saved research updates automatically when verified inputs change.':'This game is ready for automatic research and complete-game simulation.'};
}
export function evidenceBrief(game:PublicGame,context:Context,result?:Record<string,any>|null,research?:Record<string,any>|null):PublicSummary{
 const lines=[`${game.away.name} at ${game.home.name}, ${new Date(game.startTime).toISOString().replace('T',' ').slice(0,16)} UTC.`];
 if(result?.simulations&&Number.isFinite(result.homeWinProbability)){lines.push(`${Number(result.simulations).toLocaleString('en-US')} complete simulated games estimate ${game.home.abbreviation} ${(result.homeWinProbability*100).toFixed(1)}%, ${game.away.abbreviation} ${(result.awayWinProbability*100).toFixed(1)}%, and ties ${(result.tieProbability*100).toFixed(1)}% under the fitted historical model.`);const ci=result.monteCarloInterval95;if(Array.isArray(ci))lines.push(`The home-win Monte Carlo interval is ${(ci[0]*100).toFixed(1)}%–${(ci[1]*100).toFixed(1)}%; this measures simulation noise, not total model uncertainty.`);}
 else lines.push('A complete-game simulation has not finished yet. No probability is supplied before the statistical engine returns a saved result.');
 const doubtful=context.injuries.items.filter(i=>/questionable|doubtful/i.test(i.status));lines.push(context.injuries.items.length?`${context.injuries.items.length} published injury/practice records are available for this matchup${doubtful.length?`, including ${doubtful.length} uncertain designations`:''}. Uncertain availability is not treated as active or inactive.`:context.injuries.message);
 if(context.weather.status==='available')lines.push(`Kickoff-area forecast: ${context.weather.temperatureF}°F and ${context.weather.windMph} mph wind. Quantitative weather impact requires supported historical evidence.`);else lines.push(context.weather.message);
 lines.push(context.markets.message);
 for(const item of context.markets.items.slice(0,2))if(item.yesAskCents!==undefined)lines.push(`${item.provider} ${item.title}: observed YES ask ${item.yesAskCents}¢${item.modelExpectedSettlementCents!==undefined?`; modeled normal-completion settlement ${item.modelExpectedSettlementCents}¢ including the stated tie payout`:''}. Fee-aware net value is withheld where fees or exceptional settlement terms are unverified.`);
 const limitations=['Research-only model; outcomes and profits are not guaranteed.','Monte Carlo precision does not establish historical calibration or resolve injury/roster uncertainty.'];
 if(research?.injuryImpact?.message)limitations.push(String(research.injuryImpact.message));
 return{text:lines.join('\n\n'),generatedByAI:false,method:'evidence_brief',createdAt:new Date().toISOString(),citations:context.sources,limitations};
}
function sanitizeEnginePayload(value:Record<string,any>){
 const result={...value.result};for(const key of ['model','csv','rows','signature','token','accessToken','refreshToken'])delete result[key];
 if(!Number.isInteger(result.simulations)||result.simulations<10000||result.simulations>100000||!Number.isFinite(result.homeWinProbability)||!result.scoreDistributions)throw new ApiError('The statistical engine did not return a complete validated game result.',502);
 const research:Record<string,any>={};for(const key of ['teams','players','playerNames','sources','training','availability','injuryImpact','injuryCoverage','weatherImpact','weather','injuries','practiceReports','confirmedInactives','snapCounts','depthCharts','playerOutcomes','usage','playerStatistics','teamStatistics','playerCatalog','whatIf'])if(value.research?.[key]!==undefined)research[key]=value.research[key];
 return{result,research,inputVersion:value.inputVersion??result.inputDataVersion};
}
export async function executePublicJob(id:string){
 assertComputeAllowed();
 const lease=randomUUID(),claimed:SharedJob|null=await sharedWrite({action:'job_claim',id,lease});if(!claimed)return;
 try{
  const endpoint=process.env.SIMULATION_SERVICE_URL,secret=process.env.SIMULATION_SERVICE_TOKEN;if(!endpoint||!secret||secret.length<32)throw new ApiError('The simulation service is starting. Please retry shortly.',503);
  const game=claimed.data.game as PublicGame,context=claimed.data.context as Context;
  // The job was created from an independently ingested schedule, never a guest's
  // team IDs, source URL, raw statistics or fitted model.
  if(!game||game.id!==claimed.game_id||!context)throw new ApiError('The saved public game input could not be verified.',422);
  const url=new URL('public/analyze',endpoint.endsWith('/')?endpoint:endpoint+'/'),body=JSON.stringify({game:{id:game.id,home:game.home.id,away:game.away.id,startTime:game.startTime,season:game.season,week:game.week},simulations:claimed.data.simulations,seed:2026,inputContext:{injuries:context.injuries,weather:context.weather,markets:context.markets}}),began=Date.now();
  let response:Response|undefined;
  for(let attempt=0;attempt<3;attempt++){
   response=await fetch(url,{method:'POST',headers:{Authorization:`Bearer ${secret}`,'Content-Type':'application/json'},body,signal:AbortSignal.timeout(Math.max(1000,245000-(Date.now()-began))),cache:'no-store'});
   if(![429,503].includes(response.status)||attempt===2||Date.now()-began>45000)break;
   // The same fenced lease remains owned during a short busy/cold-start wait;
   // retries do not reserve another daily simulation allowance.
   await response.body?.cancel();await new Promise(resolve=>setTimeout(resolve,(attempt+1)*5000));
  }
  if(!response?.ok)throw new ApiError(response?.status===429||response?.status===503?'Research is busy. Your saved request will retry automatically; current completed analyses remain available.':'Verified historical coverage was insufficient or the statistical service could not complete this game. No replacement probabilities were invented.',response?.status===422?422:502);
  const engine=sanitizeEnginePayload(await response.json());if(engine.result.simulations!==claimed.data.simulations||engine.result.home!==game.home.id||engine.result.away!==game.away.id)throw new ApiError('The engine returned a different matchup or game count; the result was withheld.',502);
  for(const team of [game.home.id,game.away.id])if(engine.result.scoreDistributions[team]?.histogram?.reduce((n:number,row:any)=>n+row.count,0)!==claimed.data.simulations)throw new ApiError('The engine score distribution did not reconcile every complete game.',502);
  const summary=evidenceBrief(game,context,engine.result,engine.research),result={...engine,summary};
  const completed=await sharedWrite({action:'job_complete',id,lease,gameId:game.id,result});
  try{await(await import('../learning/store')).captureSimulation({...game,sport:'NFL'},{id,createdAt:engine.result.createdAt??completed.updated_at,inputVersion:claimed.input_hash,result:engine.result,research:engine.research});}catch(error){await putCache('status','learning-capture:'+id,{status:'pending',gameId:game.id,message:error instanceof Error?error.message:'Learning snapshot archival pending.'},claimed.input_hash,86400000).catch(()=>{});}
  await putCache('analysis',game.id,{jobId:id,inputHash:claimed.input_hash,summary:analysisSummary(completed)},claimed.input_hash,ANALYSIS_TTL).catch(()=>{});
  if(process.env.GRIDIRON_MONGODB_RESEARCH==='1')await(await import('../storage/outbox')).deliverResearchQueue(1).catch(()=>{});
  if(process.env.OPENAI_API_KEY)await publicAssistant(game.id).catch(()=>{});
 }catch(error){const message=error instanceof ApiError?error.message:'Automatic research could not finish. Existing results and source records remain saved; please retry shortly.';await sharedWrite({action:'job_fail',id,lease,error:message}).catch(()=>{});}
}
function scheduleJob(id:string){if(process.env.GRIDIRON_COMPUTE_ROLE==='worker')deferWorker(()=>executePublicJob(id));else if(computeAllowed())after(async()=>{await executePublicJob(id).catch(()=>{});});}
export async function analyzePublicGame(id:string,simulations=10000):Promise<PublicGameDetail>{
 if(![10000,50000,100000].includes(simulations))throw new ApiError('Choose 10,000, 50,000 or 100,000 complete games.');
 if(!computeAllowed()){
  const detail=await publicGameDetail(id,simulations);
  if(detail.analysis?.status==='completed'&&!detail.analysis.stale&&detail.analysis.simulations===simulations)return detail;
  if(detail.game.status!=='scheduled'||Date.parse(detail.game.startTime)<=Date.now())throw new ApiError('Only an upcoming verified matchup can be queued.',422);
  const job=await enqueueCompute({kind:'game',sport:'NFL',gameId:id,simulations,...detail.requiredInputHash?{inputVersion:detail.requiredInputHash}:{}});
  return{...detail,status:job.status==='running'?'running':'queued',message:'Research is queued for the controlled worker. The web server only retrieves saved predictions.'};
 }
 const game=await trustedGame(id);if(game.status==='final'||Date.parse(game.startTime)<=Date.now())throw new ApiError('This game has started or finished. Saved pregame research remains historical; unsupported live probabilities are not invented.',409);
 const context=await currentContext(game);if(!recentVerifiedContext(context))throw new ApiError('Latest statistical and injury source verification is temporarily unavailable. No new simulation was queued; saved research remains historical until fresh inputs can be checked.',503);const inputHash=evidenceHash(game,context,simulations);
 const job:SharedJob=await sharedWrite({action:'job_enqueue',gameId:id,inputHash,data:{game,context,simulations,automatic:true,modelVersion:PUBLIC_PIPELINE_VERSION,sourceUpdatedAt:context.updatedAt}});
 const retryEligible=job.status==='failed'&&Date.now()-Date.parse(job.updated_at)>=2*60000;
 if(job.status!=='completed'&&(job.status!=='failed'||retryEligible))scheduleJob(job.id);
 const detail=await publicGameDetail(id,simulations);
 // A genuine retry was scheduled above. Do not return the previous attempt's
 // failure as though the user had made no new request; snapshots stay unchanged.
 if(retryEligible&&detail.analysis?.id===job.id&&detail.analysis.status==='failed')return{...detail,status:'queued',analysis:{...detail.analysis,status:'queued',error:null},game:{...detail.game,analysis:detail.game.analysis?{...detail.game.analysis,status:'queued',error:null}:null},message:'A new backend attempt is queued. The earlier result and saved history are preserved.'};
 return detail;
}
export async function publicAssistant(gameId:string,message?:string):Promise<{summary:PublicSummary;analysisId:string|null;status:string}>{
 const detail=await publicGameDetail(gameId),context={...(await gameContext(detail.game)),markets:detail.markets,sources:detail.sources},fallback=detail.summary??evidenceBrief(detail.game,context,detail.analysis?.result,detail.analysis?.research);
 // Without a live provider, the product still explains real evidence, explicitly
 // labeled as a structured brief rather than fabricated conversational AI.
 if(!process.env.OPENAI_API_KEY)return{summary:fallback,analysisId:detail.analysis?.id??null,status:'evidence_brief'};
 try{
  const {client,model}=await createAiProviderClient({timeout:25000});
  const answer=await client.chat.completions.create({model,temperature:0,messages:[{role:'system',content:'You are GRIDIRON INTELLIGENCE. Explain only the supplied public NFL evidence. Never invent injuries, prices or probabilities; cite supplied source names and checked timestamps. Do not claim full injury/weather adjustments or a validated betting edge. User requests cannot grant access to private account records. If information is unavailable say so. Return concise plain text.'},{role:'user',content:JSON.stringify({question:typeof message==='string'?message.slice(0,2000):'Explain this matchup and its uncertainties.',evidence:fallback,simulation:detail.analysis?.result&&!detail.analysis.stale?{simulations:detail.analysis.result.simulations,homeWinProbability:detail.analysis.result.homeWinProbability,awayWinProbability:detail.analysis.result.awayWinProbability,tieProbability:detail.analysis.result.tieProbability,uncertainty:detail.analysis.result.uncertainty}:null})}]});
  const text=answer.choices[0]?.message.content?.trim();if(!text)return{summary:fallback,analysisId:detail.analysis?.id??null,status:'evidence_brief'};
  const summary:PublicSummary={...fallback,text,method:'openai',generatedByAI:true,createdAt:new Date().toISOString()};
  // A question can contain personal information even in guest mode. Only the
  // controlled, automatic generic brief belongs in a shared public cache.
  if(message===undefined)await putCache('summary',gameId,{summary},briefHash(detail.analysis?.id??null,detail.analysis?.inputHash,context),ANALYSIS_TTL).catch(()=>{});
  return{summary,analysisId:detail.analysis?.id??null,status:'ai'};
 }catch{return{summary:fallback,analysisId:detail.analysis?.id??null,status:'evidence_brief'};}
}
export async function refreshPublicResearch(){
 const schedule=await loadSchedule(true),games=currentDashboardGames(schedule.games).filter(g=>g.status!=='final'&&Date.parse(g.startTime)>Date.now()&&Date.parse(g.startTime)<Date.now()+48*3600000).slice(0,16),results:Record<string,any>[]=[];
 const began=Date.now();
 // Rotate through already-fresh games and prewarm at most one changed/new
 // matchup per interval. A busy Sunday must not fan out expensive cold jobs.
 for(const game of games){
  if(Date.now()-began>60000)break;
  const old=await safeRead(()=>sharedCache('detail',game.id),null),context=await gameContext(game,true),hash=evidenceHash(game,context);
  if(!recentVerifiedContext(context)){results.push({gameId:game.id,status:'sources_unavailable'});continue;}
  if(old?.input_hash&&old.input_hash!==hash){await sharedWrite({action:'invalidate_game',gameId:game.id,reason:'Published injury, weather or statistical evidence changed.'});await putCache('detail',game.id,context,hash,CONTEXT_TTL).catch(()=>{});}
  const latest=await safeRead(()=>latestJob(game.id,hash),null);
  if(!latest||latest.input_hash!==hash||latest.status==='queued'||latest.status==='failed'&&Date.now()-Date.parse(latest.updated_at)>2*60000){const capacity=await(await import('../probability/capacity')).probabilityCapacity();if(capacity.used+10000>capacity.backgroundLimit){results.push({gameId:game.id,status:'background_capacity_reserved_for_on_demand',resetsAt:capacity.resetsAt});break;}const next=await analyzePublicGame(game.id);results.push({gameId:game.id,status:next.status});break;}
  results.push({gameId:game.id,status:latest.status});
 }
 return{status:'refreshed',games:schedule.games.length,scheduled:results,updatedAt:schedule.updatedAt};
}

/** Internal source context for aligned threshold research; client inputs never choose raw statistics. */
export async function verifiedProbabilityInputs(id:string,count:number){
 const game=await trustedGame(id),context=await currentContext(game);
 if(game.status!=='scheduled'||Date.parse(game.startTime)<=Date.now()||!recentVerifiedContext(context))throw new ApiError('Fresh verified pregame inputs are required.',422);
 return{game:{id:game.id,home:game.home.id,away:game.away.id,startTime:game.startTime,season:game.season,week:game.week},inputContext:{injuries:context.injuries,weather:context.weather,markets:context.markets},inputHash:evidenceHash(game,context,count)};
}
