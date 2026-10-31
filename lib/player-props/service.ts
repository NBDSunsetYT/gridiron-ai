import {randomUUID} from 'node:crypto';
import {after} from 'next/server';
import {ApiError} from '../auth';
import {sharedJob,latestJobs} from '../public-nfl/store';
import {loadSchedule,publicGameDetail,analyzePublicGame,PUBLIC_PIPELINE_VERSION,evidenceHash} from '../public-nfl/service';
import {sha} from '../public-nfl/sources';
import {discoverPlayerPropMarkets,fetchPlayerPropMarkets,draftKingsFeedConfigured} from './providers';
import {resolvePlayerPropIdentity,recheckPropMarketFreshness} from './normalize';
import {buildPropResearch,exactPropDistribution,valueProp} from './math';
import {applyPropCalibration,type PropCalibrator} from './evaluation';
import {propWrite,propRun,propBatch,storedContracts,storeContracts,storeResearch,researchPage,currentContracts,storedResearch,cachedGameStates,type PropFilters} from './store';
import type {PropMarketContract,PropPlayerIdentity} from './market-types';
import {isGameMarket} from './market-types';
import {exactGameDistribution} from './game-math';
import type {PropScan,PropRun,PropResearch} from './types';
import type {PublicGame,PublicGameDetail} from '../public-nfl/types';

const MAX_SCAN_AGE=90000;
export const NFL_MARKET_PIPELINE_VERSION='nfl-event-contract-research-7.0.0';
const safe=async<T>(work:()=>Promise<T>,fallback:T):Promise<T>=>{try{return await work();}catch{return fallback;}};
function dispatch(id:string){after(async()=>{await executePropRun(id);});}
function selectedGames(games:PublicGame[]){return games.filter(game=>game.status!=='final'&&Date.parse(game.startTime)>Date.now()&&Date.parse(game.startTime)<Date.now()+7*86400000);}
async function performance(){try{const module=await import('./model-lab');return await module.getPropPerformance();}catch{return{status:'unavailable',eligibleResolved:null,overall:null,message:'Historical model performance could not be verified right now. Existing observations remain preserved; unavailable metrics are not zero accuracy.'};}}

export async function startPropScan(trigger='user',provider:'DraftKings Predictions'|'Kalshi'='DraftKings Predictions'){
 if(provider==='DraftKings Predictions'&&!draftKingsFeedConfigured())throw new ApiError('Authorized DraftKings Predictions NFL contract data is unavailable. No alternative-exchange research was queued.',503);
 const current=await propRun();
 if(current&&current.data.provider===provider&&current.data.pipelineVersion===NFL_MARKET_PIPELINE_VERSION&&(['queued','running'].includes(current.status)||Date.now()-Date.parse(current.updated_at)<(current.status==='failed'?15000:MAX_SCAN_AGE))){if(current.status==='queued'||current.status==='running'&&Date.now()-Date.parse(current.updated_at)>4*60000)dispatch(current.id);return current;}
 const schedule=await loadSchedule(),games=selectedGames(schedule.games);
 const run:PropRun=await propWrite({action:'run_enqueue',inputHash:sha({version:NFL_MARKET_PIPELINE_VERSION,provider,previousFailure:current?.status==='failed'?current.id:null,period:Math.floor(Date.now()/60000),games:games.map(game=>game.id)}),data:{trigger,provider,pipelineVersion:NFL_MARKET_PIPELINE_VERSION,phase:'discover',gameIds:games.map(game=>game.id),processedGames:[],failedGames:[],startedAt:new Date().toISOString(),previousRunId:current?.id??null}});
 dispatch(run.id);return run;
}
function header(run:PropRun|null,games:PublicGame[]):Omit<PropScan,'results'|'performance'|'totalResults'|'nextCursor'>{const result=run?.result??{};return{status:run?.status??'unavailable',message:run?.error??undefined,runId:run?.id??null,updatedAt:run?.updated_at??new Date().toISOString(),games,providers:result.providers??[],progress:result.progress??{completed:0,total:0,phase:'Ready to discover verified contracts',gamesComplete:0,gamesTotal:0},sources:result.sources??[],limitations:result.limitations??['No authorized live DraftKings Predictions feed is configured. Available alternatives are labeled by their actual provider.','Raw simulation estimates are not calibrated probabilities or proof of positive expected value.']};}
export async function propDashboard(filter:PropFilters={}):Promise<PropScan>{
 const provider=filter.provider??'DraftKings Predictions';
 if(provider==='DraftKings Predictions'&&!draftKingsFeedConfigured())return unavailableDraftKingsDashboard('player',{...filter,provider});
 return marketDashboard({...filter,scope:'player',provider});
}
export async function nflMarketDashboard(filter:PropFilters={}):Promise<PropScan>{
 if((filter.provider??'DraftKings Predictions')==='DraftKings Predictions'&&!draftKingsFeedConfigured())return unavailableDraftKingsDashboard(filter.scope??'all',filter);
 return marketDashboard({...filter,scope:filter.scope??'all',provider:filter.provider??'DraftKings Predictions'});
}
async function unavailableDraftKingsDashboard(scope:'all'|'player'|'game',filter:PropFilters):Promise<PropScan>{
 const schedule=await loadSchedule(),at=new Date().toISOString(),message='An authorized DraftKings Predictions NFL event-contract feed is not connected. No alternative market prices or alternative simulations are substituted. You can browse verified NFL games or explicitly select a separately labelled exchange.';
 return{status:'unavailable',message,runId:null,resultSetId:null,updatedAt:at,games:selectedGames(schedule.games),providers:[{provider:'DraftKings Predictions',status:'unavailable',checkedAt:at,contracts:0,message,sourceUrl:'https://predictions.draftkings.com/en',categories:[]},{provider:'Kalshi',status:'unavailable',checkedAt:at,contracts:0,message:'Optional separate exchange. Select Kalshi explicitly to retrieve its own contracts; these are not DraftKings Predictions prices.',sourceUrl:'https://docs.kalshi.com/getting_started/quick_start_market_data',categories:[]}],results:[],progress:{completed:0,total:0,phase:'DraftKings Predictions contract feed unavailable',gamesComplete:0,gamesTotal:0},sources:schedule.sources,limitations:[message,'A percentage price is distinct from executable bid/ask, after-fee break-even and calibrated model probability.'],performance:{status:'unavailable',n:null,brier:null,logLoss:null,message:'No current authorized DraftKings contract archive is connected; unavailable evidence is not zero model accuracy.'},totalResults:0,nextCursor:null,primaryProvider:'DraftKings Predictions',marketScope:scope,ranking:filter.ranking??'coverage'};
}
async function marketDashboard(filter:PropFilters):Promise<PropScan>{
 let readUnavailable=false;const [schedule,run]=await Promise.all([loadSchedule(),propRun().catch(()=>{readUnavailable=true;return null;})]),games=selectedGames(schedule.games);
 if(run?.data.pipelineVersion===NFL_MARKET_PIPELINE_VERSION&&(run.status==='queued'||run.status==='running'&&Date.now()-Date.parse(run.updated_at)>4*60000))dispatch(run.id);
 let pageRun=run?.id??null;const pinned=filter.cursor?.match(/^([a-f0-9-]{36}):(\d+)$/i);if(pinned){pageRun=pinned[1];filter={...filter,cursor:pinned[2]};}
 let page=pageRun?await researchPage(pageRun!,filter).catch(()=>{readUnavailable=true;return{rows:[] as PropResearch[],total:0,nextCursor:null};}):{rows:[],total:0,nextCursor:null};
 if(!pinned&&run&&['queued','running','failed','unavailable'].includes(run.status)&&!page.total&&run.data?.previousRunId){pageRun=run.data.previousRunId;page=await safe(()=>researchPage(pageRun!,filter),page);}
 const market=await safe(()=>currentContracts([...new Set(page.rows.map(row=>row.contract.id))]),new Map<string,PropMarketContract>());
 const contexts=page.rows.length?await safe(()=>cachedGameStates(page.rows.map(row=>row.game.id)),new Map<string,any>()):new Map<string,any>();
 const required=new Map<string,string>();for(const [gameId,context] of contexts){const age=Date.now()-Date.parse(context.updated_at);if((context.verified===true||context.verified==='true')&&context.pipeline===PUBLIC_PIPELINE_VERSION&&Number.isFinite(age)&&age>=-60000&&age<=30*60000&&typeof context.input_hash==='string')required.set(gameId,context.input_hash);}
 const matching=required.size?await safe(()=>latestJobs(100,[...required.values()]),[]):[],byHash=new Map(matching.map(job=>[job.input_hash,job]));
 const playerPerformance=await performance();let report:Record<string,unknown>=playerPerformance;
 if(filter.scope!=='player'){try{const gameLab=await import('./game-performance');report={playerMarkets:playerPerformance,gameMarkets:await gameLab.getGameMarketPerformance(),message:'Player and game-contract reliability are separate; unavailable categories are not assigned a calibrated probability.'};}catch{report={playerMarkets:playerPerformance,gameMarkets:{status:'unavailable',n:null,brier:null,logLoss:null,message:'Game-contract historical performance could not be verified.'}};}}
 // Every await, including potentially slow historical metrics, precedes the
 // final quote-age check. A stale capture boolean cannot survive response time.
 const results=page.rows.map(row=>{const value=hydrateCurrent(row,market.get(row.contract.id)),hash=required.get(row.game.id),current=hash?byHash.get(hash):null;if(row.simulationId&&(!hash||!current||current.input_hash!==hash||current.id!==row.simulationId||current.status!=='completed'))return{...value,modelInputsCurrent:false,stale:true,status:'stale' as const,...value.rankingMetrics?{rankingMetrics:{...value.rankingMetrics,calibratedProbability:null,modelMarketDifference:null,historicalSupport:null,uncertaintyWidth:null,injuryChange:null}}:{},currentValuation:{breakEven:null,fairCents:null,netValueCents:null,entryCostCents:null,feesVerified:false,reason:'Current game inputs could not be verified or a newer simulation is pending. This immutable snapshot remains historical.'}};return{...value,modelInputsCurrent:Boolean(hash&&current?.id===row.simulationId&&current?.status==='completed')};});
 if(run&&!/preserve personal.record storage|storage capacity needs|storage review|required.*storage|daily.*budget|budget.*limit/i.test(run.error??'')&&!['queued','running'].includes(run.status)&&Date.now()-Date.parse(run.updated_at)>MAX_SCAN_AGE&&(filter.provider==='Kalshi'||draftKingsFeedConfigured()))after(async()=>{await startPropScan('automatic',filter.provider??'DraftKings Predictions').catch(()=>{});});
 const paginationStable=Boolean(pageRun&&(!run||pageRun!==run.id||!['queued','running'].includes(run.status)));
 return{...header(run,games),...readUnavailable?{status:'failed' as const,message:'Saved research storage is temporarily unavailable. Existing contracts and snapshots are preserved; an empty response is not evidence that no markets exist.'}:{},resultSetId:pageRun,results,performance:report,totalResults:page.total,paginationStable,nextCursor:paginationStable&&page.nextCursor&&pageRun?pageRun+':'+page.nextCursor:null,primaryProvider:'DraftKings Predictions',marketScope:filter.scope??'player',ranking:filter.ranking??'coverage',rankingMeaning:filter.ranking==='disagreement'?'Absolute model minus fresh market ask, before fees and settlement exceptions. A disagreement is not proof of positive expected value.':filter.ranking==='uncertainty'?'Parameter-sensitivity interval width, not calibrated model certainty.':'Rankings use only verified available evidence; unsupported metrics are excluded rather than invented.'};
}
export function hydrateCurrent(row:PropResearch,current?:PropMarketContract):PropResearch{
 const contract=recheckPropMarketFreshness(current??row.contract),stale=!contract.verification.current;
 const same=['id','gameId','eventId','playerId','team','stat','threshold','operator','rulesHash','eventStart'].every(key=>(contract as any)[key]===(row.contract as any)[key])&&(!isGameMarket(row.contract.stat)||JSON.stringify(contract.subject)===JSON.stringify(row.contract.subject));
 if(!same)return{...row,currentContract:contract,currentValuation:{breakEven:null,fairCents:null,netValueCents:null,entryCostCents:null,feesVerified:false,reason:'The current contract definition no longer matches the immutable player/game/threshold/rules snapshot. Current comparisons are withheld.'},stale:true,status:'stale',updatedAt:contract.observedAt};
 return{...row,currentContract:contract,currentValuation:valueProp(contract,row.side,row.probability.calibrated??row.probability.raw),stale,status:row.status==='withheld'?'withheld':stale?'stale':row.probability.conditional?'conditional':'available',updatedAt:contract.observedAt};
}
export async function propResearchDetail(id:string){
 if(!/^[a-f0-9]{64}$/.test(id))throw new ApiError('Player research snapshot not found.',404);
 const row=await storedResearch(id);if(!row)throw new ApiError('Player research snapshot not found.',404);
 const [market,detail]=await Promise.all([currentContracts([row.contract.id]),safe(()=>publicGameDetail(row.game.id),null)]);
 const response=hydrateCurrent(row,market.get(row.contract.id));
 if(row.simulationId){const job=await sharedJob(row.simulationId);if(job?.result?.result){response.distribution=isGameMarket(row.contract.stat)?exactGameDistribution(job.result.result,row.contract):row.player.id?exactPropDistribution(job.result.result,row.player.id,row.contract.stat):null;response.sources=detail?.sources??row.sources;}}
 response.modelInputsCurrent=detail?.analysis?.id===row.simulationId&&detail?.analysis?.status==='completed'&&!detail?.analysis?.stale;
 if(!response.modelInputsCurrent){response.stale=true;response.status='stale';response.currentValuation={breakEven:null,fairCents:null,netValueCents:null,entryCostCents:null,feesVerified:false,reason:'Game inputs or model version changed. Re-run the current scanner before comparing this historical probability with a fresh price.'};}
 return finalizeMarketFreshness(response);
}
export function finalizeMarketFreshness(row:PropResearch,now:number|Date=Date.now()):PropResearch{
 const current=recheckPropMarketFreshness(row.currentContract??row.contract,now);if(current.verification.current)return{...row,currentContract:current};
 return{...row,currentContract:current,stale:true,status:row.status==='withheld'?'withheld':'stale',...row.rankingMetrics?{rankingMetrics:{...row.rankingMetrics,modelMarketDifference:null,priceChange:null,modelMarketDifferenceBasis:null}}:{},currentValuation:{breakEven:null,fairCents:null,netValueCents:null,entryCostCents:null,feesVerified:false,reason:'This quote expired or is not a verified current offer. Historical contract prices and probabilities remain unchanged.'}};
}
function preserveResolved(contract:PropMarketContract,old?:PropMarketContract){
 return old?.playerId&&contract.playerId===null?{...contract,playerId:old.playerId,position:old.position}:contract;
}
export function attachApprovedPropCalibration(row:PropResearch,artifact:PropCalibrator|undefined):PropResearch{
 if(isGameMarket(row.contract.stat))return row;
 if(row.probability.raw===null||!row.modelVersion||!artifact)return row;
 const yes=row.side==='YES'?row.probability.raw:1-row.probability.raw;
 const calibrated=applyPropCalibration(yes,artifact,{category:row.contract.stat,modelVersion:row.modelVersion,predictedAt:row.capturedAt});
 if(calibrated===null)return row;
 const p=row.side==='YES'?calibrated:1-calibrated,checks=row.dataQuality.checks.map(check=>check.name.startsWith('Validated calibration')?{...check,passed:true}:check);
 return{...row,id:sha([row.id,'approved_calibration',artifact.id]),probability:{...row.probability,calibrated:p,calibrationArtifactId:artifact.id,calibrationStatus:'Validated against a separate subsequent chronological game-block holdout; the artifact and original raw estimate are preserved.',historicalSampleSize:artifact.validation?.sampleSize??0},valuation:valueProp(row.contract,row.side,p),dataQuality:{...row.dataQuality,checks,score:Math.round(100*checks.filter(check=>check.passed).length/checks.length)},assumptions:[...row.assumptions,'The Monte Carlo interval describes the raw simulation rate. It is not a confidence interval for the calibrated transformation.']};
}
async function checkpoint(run:PropRun,lease:string,data:Record<string,any>,status:PropRun['status'],result:Record<string,any>,error?:string){return propWrite({action:'run_checkpoint',id:run.id,lease,status,data,result,...error?{error}:{}});}
export async function executePropRun(id:string,deadline=Date.now()+210000){
 const lease=randomUUID(),run:PropRun|null=await propWrite({action:'run_claim',id,lease});if(!run)return;
 const data={...run.data},previous=run.result??{};
 try{
  const schedule=await loadSchedule(),games=selectedGames(schedule.games),byGame=new Map(games.map(game=>[game.id,game]));
  if(data.phase==='discover'){
   const discovery=await discoverPlayerPropMarkets(games,{includeGameMarkets:true,provider:data.provider??'DraftKings Predictions'}),grouped=new Map<string,PropMarketContract[]>();
   for(const contract of discovery.contracts){const list=grouped.get(contract.gameId)??[];list.push(contract);grouped.set(contract.gameId,list);}
   for(const [gameId,contracts] of grouped){const old=new Map((await storedContracts(gameId)).map(contract=>[contract.id,contract]));await storeContracts(contracts.map(contract=>preserveResolved(contract,old.get(contract.id))));}
   const target=[...grouped.keys()].sort((a,b)=>Date.parse(byGame.get(a)!.startTime)-Date.parse(byGame.get(b)!.startTime));
   data.phase='research';data.targetGames=target;data.processedGames=[];data.failedGames=[];data.contractCount=discovery.contracts.length;data.discoveryComplete=discovery.complete;data.activeContractIds=discovery.contracts.map(contract=>contract.id);data.discoveryCheckedAt=discovery.checkedAt;
   const result={providers:discovery.providers,sources:discovery.sources,limitations:['DraftKings Predictions contracts are available only with an authorized feed; separately labeled public exchange contracts are not claimed equivalent.','Non-participation and exceptional settlement may make raw probabilities conditional. Fee-aware value is withheld where unsupported.','Calibration is not invented; current estimates remain an incompletely injury-adjusted historical baseline.'],progress:{completed:0,total:discovery.contracts.length*2,phase:target.length?'Preparing current statistics, injuries and complete-game simulations':'No verified available player contracts were supplied',gamesComplete:0,gamesTotal:target.length},rejected:discovery.rejected.slice(0,30),discoveryComplete:discovery.complete};
   await checkpoint(run,lease,data,target.length?'queued':'unavailable',result);return;
  }
  const target=(data.targetGames??[]) as string[],done=(data.processedGames??[]) as string[],failures=(data.failedGames??[]) as string[],remaining=target.filter(gameId=>!done.includes(gameId)&&!failures.includes(gameId));
  if(!remaining.length){await checkpoint(run,lease,data,failures.length||!data.discoveryComplete?'partial':'completed',{...previous,progress:{...previous.progress,phase:failures.length?'Research completed with explicit evidence limits':'Available contract research saved',gamesComplete:done.length}});return;}
  const gameId=remaining[0],game=byGame.get(gameId);
  if(!game){data.failedGames=[...failures,gameId];await checkpoint(run,lease,data,'queued',{...previous,progress:{...previous.progress,phase:'A game has started; pregame predictions were withheld'}});return;}
  let detail=await publicGameDetail(gameId);
  if(!detail.analysis||detail.analysis.stale||detail.analysis.status!=='completed'){
   if(detail.analysis?.status==='failed'&&(data.retriedGames??[]).includes(gameId)){data.failedGames=[...failures,gameId];await checkpoint(run,lease,data,'queued',{...previous,progress:{...previous.progress,phase:'Insufficient current game evidence; continuing other games'},gameFailures:[...(previous.gameFailures??[]),{gameId,message:detail.analysis.error}]});return;}
   if(detail.analysis?.stale||!['queued','running'].includes(detail.analysis?.status??'')){if(detail.analysis?.status==='failed')data.retriedGames=[...(data.retriedGames??[]),gameId];detail=await analyzePublicGame(gameId);}
   await checkpoint(run,lease,data,'queued',{...previous,progress:{...previous.progress,phase:`Simulating ${game.away.abbreviation} at ${game.home.abbreviation}: 10,000 complete games`}});return;
  }
  const catalog=(detail.analysis.research?.playerCatalog??[]) as PropPlayerIdentity[];
  const existing=await storedContracts(gameId),old=new Map(existing.map(contract=>[contract.id,contract]));
  const activeIds=Array.isArray(data.activeContractIds)?new Set<string>(data.activeContractIds):null;
  const recent=activeIds?existing.filter(contract=>activeIds.has(contract.id)&&Date.now()-Date.parse(contract.observedAt)<90000):[];
  const sourceContracts=recent.length&&Date.now()-Date.parse(data.discoveryCheckedAt??'')<90000?recent:(await fetchPlayerPropMarkets([game],catalog,{force:true,includeGameMarkets:true,provider:data.provider??'DraftKings Predictions'})).contracts;
  const contracts=sourceContracts.map(contract=>preserveResolved(resolvePlayerPropIdentity(contract,catalog),old.get(contract.id)));
  if(!contracts.length){data.failedGames=[...failures,gameId];await checkpoint(run,lease,data,'queued',{...previous,progress:{...previous.progress,phase:'Current quotes could not be verified for one game'},gameFailures:[...(previous.gameFailures??[]),{gameId,message:'No currently verified player contracts were returned; stale prices were not substituted.'}]});return;}
  const persisted=await storeContracts(contracts.map(contract=>preserveResolved(contract,old.get(contract.id)))),quoteIds=new Map<string,string>();
  persisted.forEach((row:any)=>quoteIds.set(row.id,row.quoteId));
  const lab=await import('./model-lab'),calibrators=await lab.loadApprovedPropCalibrators();
  const rows=contracts.flatMap(contract=>(['YES','NO'] as const).map(side=>{const raw=buildPropResearch(contract,detail,side,run.id);return attachApprovedPropCalibration(raw,calibrators.get(contract.stat+'|'+raw.modelVersion));}));
  await storeResearch(rows,quoteIds,run.id);
  data.processedGames=[...done,gameId];data.processedOutcomes=Number(data.processedOutcomes??0)+rows.length;
  const complete=data.processedGames.length+failures.length===target.length;
  await checkpoint(run,lease,data,complete?(failures.length||!data.discoveryComplete?'partial':'completed'):'queued',{...previous,progress:{completed:data.processedOutcomes,total:Math.max(data.contractCount*2,data.processedOutcomes),phase:complete?'Verified player research saved':'Saving current contract research and preparing the next game',gamesComplete:data.processedGames.length,gamesTotal:target.length},updatedAt:new Date().toISOString()});
  if(!complete&&Date.now()<deadline)await executePropRun(id,deadline);
 }catch(error){await checkpoint(run,lease,data,'failed',{...previous,progress:{...(previous.progress??{}),phase:'Research paused; saved snapshots remain available'}},error instanceof ApiError?error.message:'A source or research service could not complete this update. No replacement prices or probabilities were invented.').catch(()=>{});}
}
export async function refreshPropResearch(){
 const current=await propRun();
 // Continue an already explicitly selected source even after the phone closes.
 // This never starts an alternative scan or adopts a legacy mixed-provider run.
 if(current?.data.pipelineVersion===NFL_MARKET_PIPELINE_VERSION&&['DraftKings Predictions','Kalshi'].includes(current.data.provider)&&['queued','running'].includes(current.status)){
  await executePropRun(current.id);return{id:current.id,status:'continued'};
 }
 const provider=draftKingsFeedConfigured()?'DraftKings Predictions':process.env.GRIDIRON_KALSHI_BACKGROUND_RESEARCH==='1'?'Kalshi':null;
 if(!provider)return{id:null,status:'unavailable',message:'DraftKings feed unavailable; alternative-exchange background research was not explicitly enabled.'};
 const run=await startPropScan('scheduled',provider);return{id:run.id,status:run.status};
}
