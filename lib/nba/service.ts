import {evaluateNBAHistogram,NBAProbabilityError} from './probability';
/** Public NBA research only. Never reads Wallet records or browser API keys. */
import {createHash} from 'node:crypto';
import {ApiError} from '../auth';
import {boundedFetch} from '../public-nfl/sources';
import {sharedCache,putCache,sharedWrite,publicRateLimit} from '../public-nfl/store';
import {putResearchObject,readResearchObject,isResearchPointer} from '../public-nfl/objects';
import {sharedPublicMemo} from '../performance/shared-memo';
import {cloudContext,requireCloudUser,finishCloud} from '../cloud/context';
import {saveRecord,records,record} from '../cloud/store';
import {sportsDataBridgeConfiguration} from '../sportsbook-reference/bridge';

export const NBA_VERSION='nba-possession-rotation-candidate-15.1.1';
export function parseNBAResponse(text:string,label:string):any{try{return JSON.parse(text);}catch{throw new ApiError(label+' returned an unsupported response. No replacement prices or projections were used.',502);}}
const hash=(v:unknown)=>createHash('sha256').update(JSON.stringify(v)).digest('hex');
export type NBAGame={id:string;espnId:string;sport:'NBA';startTime:string;status:'scheduled'|'live'|'final';home:{id:string;name:string;score:number|null};away:{id:string;name:string;score:number|null};source:string;checkedAt:string};
export function normalizeNBASchedule(value:any,checkedAt=new Date().toISOString()):NBAGame[]{
 if(!Array.isArray(value?.events))throw new ApiError('The NBA schedule source returned an unsupported response.',502);
 const seen=new Set<string>();return value.events.flatMap((e:any)=>{const c=e.competitions?.[0],home=c?.competitors?.find((t:any)=>t.homeAway==='home'),away=c?.competitors?.find((t:any)=>t.homeAway==='away');if(!/^\d{1,12}$/.test(String(e.id))||seen.has(String(e.id))||!/^\d+$/.test(String(home?.team?.id))||!/^\d+$/.test(String(away?.team?.id))||home.team.id===away.team.id||!Number.isFinite(Date.parse(e.date)))return[];seen.add(String(e.id));const status=c.status?.type?.completed?'final':c.status?.type?.state==='in'?'live':'scheduled',score=(v:any)=>status==='scheduled'?null:/^\d+$/.test(String(v))?Number(v):null;return[{id:'nba:espn:'+e.id,espnId:String(e.id),sport:'NBA' as const,startTime:e.date,status:status as NBAGame['status'],home:{id:String(home.team.id),name:String(home.team.displayName),score:score(home.score)},away:{id:String(away.team.id),name:String(away.team.displayName),score:score(away.score)},source:'https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard',checkedAt}];}).sort((a:NBAGame,b:NBAGame)=>Date.parse(a.startTime)-Date.parse(b.startTime));
}
export async function nbaSchedule(){
 const date=new Date(),day=(d:Date)=>d.toISOString().slice(0,10).replaceAll('-',''),dates=Array.from({length:3},(_,i)=>day(new Date(date.getTime()+i*86400000)));
 // Reuse the existing bounded public-cache lease; the key explicitly includes
 // NBA, implementation, and requested date range. No new table is introduced.
 return sharedPublicMemo('cfb_schedule',['nba-schedule-v15',dates],{ttlMs:300000},async()=>{const urls=dates.map(d=>'https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates='+d+'&limit=100'),responses=await Promise.allSettled(urls.map(url=>boundedFetch(url,6000000,12000)));const parsed=responses.map(r=>{if(r.status==='rejected')return null;try{const value=parseNBAResponse(r.value.body.toString(),'The NBA schedule source');return Array.isArray(value.events)?value.events:null;}catch{return null;}}),events=parsed.flatMap(v=>v??[]);if(parsed.every(v=>v===null))throw new ApiError('The published NBA schedule is temporarily unavailable.',502);const checkedAt=new Date().toISOString();return{sport:'NBA',games:normalizeNBASchedule({events},checkedAt),sources:urls,checkedAt,status:parsed.some(v=>v===null)?'partial':'available'};});
}
export async function nbaMarkets(cursor=0){
 return sharedPublicMemo('market_board',['nba-propline-v15',cursor],{ttlMs:60000,leaseMs:60000},async()=>{
  const base=process.env.GRIDIRON_RENDER_DATA_URL,token=process.env.GRIDIRON_DATA_BRIDGE_TOKEN;
  const issue=sportsDataBridgeConfiguration();
  if(!base||!token||issue)return{sport:'NBA',items:[],status:'unavailable',diagnostic:issue??{code:'gateway_not_configured',message:'The authorized NBA market gateway is not connected.'}};
  const response=await fetch(new URL('/data/props/NBA?cursor='+cursor+'&limit=500',base),{headers:{Authorization:'Bearer '+token},signal:AbortSignal.timeout(25000),cache:'no-store',redirect:'error'}),raw=await response.text();
  if(raw.length>5000000||raw.includes(token))throw new ApiError('The NBA provider response failed its safe response bound.',502);
  const value=parseNBAResponse(raw,'The NBA market gateway');
  if(!response.ok)return{sport:'NBA',items:[],status:'unavailable',diagnostic:{code:response.status===422?'nba_gateway_update_required':value.diagnostic?.code??'provider_unavailable',message:response.status===422?'NBA support is awaiting the data-gateway update. Football feeds remain separate.':value.diagnostic?.message??'The NBA market source is temporarily unavailable.'}};
  if(value.sport!=='NBA'||!Array.isArray(value.items)||value.items.some((v:any)=>v.sport!=='NBA'||v.provider!=='PropLine'||v.dataFamily!=='sportsbook_reference'||v.draftKingsPredictionsEquivalent!==false))throw new ApiError('The market gateway returned a different sport or product.',502);
  const mappedEvents=value.items.filter((m:any)=>typeof m.espnEventId==='string').length,mappedPlayers=value.items.filter((m:any)=>/^espn:\d+$/.test(m.player?.id??'')).length;
  return {...value,analysisAvailability:{status:mappedEvents&&mappedPlayers?'partial_identity_coverage':'identity_mapping_unavailable',mappedEventQuotes:mappedEvents,mappedPlayerQuotes:mappedPlayers,message:'Verified sportsbook prices are available. Quotes without an exact ESPN event and player crosswalk cannot be joined to this model. Independent game simulations remain available; unsupported price comparisons are withheld.'}};
 });
}
export function nbaInputKey(game:NBAGame,inputVersion:string,availability:unknown,simulations:number){return hash(['nba-run-v15.1',{id:game.id,startTime:game.startTime,home:game.home.id,away:game.away.id},inputVersion,availability,simulations]);}
async function worker(path:string,payload:unknown,timeout=240000){
 const base=process.env.SIMULATION_SERVICE_URL,token=process.env.SIMULATION_SERVICE_TOKEN;
 if(!base||!token||token.length<32)throw new ApiError('The private NBA simulation service is not configured.',503);
 const u=new URL(path,base.endsWith('/')?base:base+'/');
 if(u.protocol!=='https:'&&!['localhost','127.0.0.1'].includes(u.hostname))throw new ApiError('A secure simulation worker is required.',503);
 const response=await fetch(u,{method:'POST',headers:{Authorization:'Bearer '+token,'Content-Type':'application/json'},body:JSON.stringify(payload),signal:AbortSignal.timeout(timeout),cache:'no-store',redirect:'error'}),text=await response.text();
 if(text.length>16000000||text.includes(token))throw new ApiError('The simulation worker response failed its safe bound.',502);
 const data=parseNBAResponse(text,'The private NBA simulation worker');if(!response.ok)throw new ApiError(typeof data.detail==='string'?data.detail:'The NBA evidence could not support a complete simulation.',response.status===422?422:response.status===429?409:502);return data;
}
async function preparedModel(){
 const old=await sharedCache('analysis','nba-v15-current-model').catch(()=>null);if(old&&Date.now()-Date.parse(old.updated_at)<6*3600000&&old.data?.model?.version===NBA_VERSION)return old.data;
 return sharedPublicMemo('cfb_prepare',['nba-model-v15',Math.floor(Date.now()/(6*3600000))],{ttlMs:600000,leaseMs:120000},async()=>{const prepared=await worker('nba/prepare',{},90000);if(prepared.model?.sport!=='NBA'||prepared.model.version!==NBA_VERSION)throw new ApiError('NBA artifact identity did not verify.',502);const pointer=await putResearchObject(prepared);await putCache('analysis','nba-v15-current-model',pointer,prepared.model.sha256,6*3600000);return prepared;});
}
export function thresholdProbability(histogram:any[],count:number,threshold:number,side:string){try{return evaluateNBAHistogram(histogram,count,threshold,side);}catch(e){if(e instanceof NBAProbabilityError)throw new ApiError(e.message,e.status);throw e;}}

export function compareNBAMarkets(result:any,markets:any[],game:NBAGame){
 return markets.filter(m=>m.sport==='NBA'&&m.espnEventId===game.espnId&&Date.parse(m.kickoff)===Date.parse(game.startTime)).map(m=>{const id=typeof m.player?.id==='string'&&/^espn:\d+$/.test(m.player.id)?'nba:'+m.player.id:null,distribution=id?result.players?.[id]?.[m.statistic]:null,at=Date.parse(m.sourceUpdatedAt),current=Number.isFinite(at)&&Date.now()-at<=300000&&at<=Date.now()+60000,periodSupported=!m.period||['full','full_game','game'].includes(m.period);let probability=null;
  if(distribution&&periodSupported&&(m.threshold!==null||m.statistic==='doubleDouble'))try{probability=thresholdProbability(distribution.histogram,result.simulations,Number(m.threshold??1),m.side);}catch{}
  return{...m,marketCurrent:current,probability,modelPlayerId:id,modelValidated:false,settlementVerified:false,marketImpliedProbability:current&&Number.isFinite(m.americanOdds)?m.americanOdds<0?Math.abs(m.americanOdds)/(100+Math.abs(m.americanOdds)):100/(100+m.americanOdds):null,expectedNetValue:null,reason:!id?'A stable NBA player crosswalk was not provided.':!distribution?'This player has no supported current rotation distribution.':!periodSupported?'This partial-game market cannot use a full-game distribution.':!probability?'The exact outcome/threshold is unsupported.':'Conditional uncalibrated research assuming full game including overtime. Lineup, settlement and model uncertainty remain.'};});
}
export async function analyzeNBAGame(request:Request,gameId:string,simulations:number){
 if(process.env.GRIDIRON_NBA_SIMULATIONS_ENABLED==='0')throw new ApiError('New NBA simulations are temporarily paused. Archived and privately saved research remains available.',503);
 await publicRateLimit(request,'nba-simulation-v15',6,3600000);
 const schedule=await nbaSchedule(),game=schedule.games.find(g=>g.id===gameId);
 if(!game||game.status!=='scheduled'||Date.parse(game.startTime)<=Date.now())throw new ApiError('Choose a verified upcoming NBA game. Historical audits use the separate evaluation pipeline.',422);
 const prepared=await preparedModel(),board=await nbaMarkets().catch(()=>({items:[],injuries:[]})),model=prepared.model,lineups:Record<string,any>={};
 const previousAvailability=await sharedCache('status','nba-availability:'+game.id).catch(()=>null);
 if(previousAvailability?.data?.hasReportedAbsence&&board.injuryCoverage!=='available')throw new ApiError('The NBA availability feed is delayed. A previously reported absence cannot be silently treated as healthy. Saved research remains available.',503);
 for(const t of [game.home,game.away]){const roster=new Set((model.teams?.[t.id]??[]).slice(-2).flatMap((g:any)=>g.roster.map((p:any)=>String(p.athlete_id))));const reported=(board.injuries??[]).filter((p:any)=>typeof p.player_id==='string'&&p.player_id.startsWith('espn:')&&roster.has(p.player_id.slice(5)));lineups[t.id]={inactive:reported.filter((p:any)=>/^(?:out|inactive|suspended)$/i.test(String(p.status_code??''))).map((p:any)=>p.player_id.slice(5)).sort(),verified:false,injuriesComplete:false,reportedAvailability:reported};}
 const materialAvailability=Object.fromEntries(Object.entries(lineups).map(([team,v])=>[team,{inactive:v.inactive,statuses:v.reportedAvailability.map((p:any)=>[p.player_id,p.status_code,p.status,p.expected_return]).sort()}]));
 if(board.injuryCoverage==='available')await putCache('status','nba-availability:'+game.id,{assumptions:materialAvailability,hasReportedAbsence:Object.values(lineups).some(v=>v.inactive.length>0),checkedAt:new Date().toISOString()},hash(materialAvailability),7*86400000);
 const key=nbaInputKey(game,model.sha256,materialAvailability,simulations);const saved=await sharedCache('analysis','nba-run:'+key).catch(()=>null);
 let analysis=saved?.data;
 if(!analysis)analysis=await sharedPublicMemo('auto_props',['nba-simulation-v15',key],{ttlMs:600000,leaseMs:300000,waitMs:3000},async()=>{const result=await worker('nba/analyze',{model,home:game.home.id,away:game.away.id,eventStart:game.startTime,simulations,seed:15002,lineups});if(result.sport!=='NBA'||result.simulations!==simulations||result.home!==game.home.id||result.away!==game.away.id||result.inputDataVersion!==model.sha256||!result.quality?.playerTeamPointsReconciled||!result.quality?.minutesReconciled)throw new ApiError('NBA simulation identity or accounting did not verify.',502);
  const inputSnapshotReference=await putResearchObject(prepared);
  const value={id:key,game,result,inputSnapshotReference,configuration:{simulations,seed:15002,batchSize:1000,engineVersion:NBA_VERSION,dependencyManifest:'modeling/requirements.txt'},codeVersion:process.env.VERCEL_GIT_COMMIT_SHA??NBA_VERSION,createdAt:new Date().toISOString(),sourceVersions:model.sources??[],modelVersion:NBA_VERSION,inputVersion:model.sha256,availabilityAssumptions:lineups,calibrated:false},pointer=await putResearchObject(value);await sharedWrite({action:'cache_put',kind:'analysis',key:'nba-run:'+key,data:pointer,inputHash:key,expiresAt:null});await putCache('status','nba-latest:'+game.id,{id:key,inputVersion:model.sha256},key,86400000);return value;});
 return{sport:'NBA',analysis,markets:compareNBAMarkets(analysis.result,board.items??[],game),marketDiagnostic:board.diagnostic??null,modelValidated:false};
}
export async function nbaSaved(request:Request,body?:{analysisId:string}){
 const ctx=await cloudContext(request);requireCloudUser(ctx);
 if(!body)return finishCloud(ctx,Response.json({records:await records(ctx,'research_records/saved_nba_simulation',{limit:50})}));
 const saved=await sharedCache('analysis','nba-run:'+body.analysisId);if(!saved?.data?.game?.id?.startsWith('nba:espn:'))throw new ApiError('Choose an existing verified NBA simulation record.',404);
 const old=await records(ctx,'research_records/saved_nba_simulation',{entityKey:body.analysisId,limit:1});if(old.length)return finishCloud(ctx,Response.json({saved:true,id:old[0].id,duplicate:true}));
 const owner=requireCloudUser(ctx),hex=hash(['owned-nba-simulation-v15',owner.id,body.analysisId]),id=hex.slice(0,8)+'-'+hex.slice(8,12)+'-5'+hex.slice(13,16)+'-a'+hex.slice(17,20)+'-'+hex.slice(20,32),pointer=await putResearchObject(saved.data);
 try{const r=await saveRecord(ctx,'research_records/saved_nba_simulation',{sport:'NBA',analysisId:body.analysisId,game:saved.data.game,reference:pointer,modelVersion:saved.data.modelVersion,inputVersion:saved.data.inputVersion},{id,entityKey:body.analysisId,source:'NBA simulation engine',observedAt:saved.data.createdAt});return finishCloud(ctx,Response.json({saved:true,id:r.id}, {status:201}));}
 catch(e){const existing=await record(ctx,id,'research_records/saved_nba_simulation').catch(()=>null);if(existing)return finishCloud(ctx,Response.json({saved:true,id,duplicate:true}));throw e;}
}
export async function readSavedNBA(request:Request,id:string){const ctx=await cloudContext(request),r=await record(ctx,id,'research_records/saved_nba_simulation');if(!isResearchPointer(r.data.reference))throw new ApiError('Saved NBA reference failed verification.',502);const analysis=await readResearchObject(r.data.reference);if(analysis.result?.sport!=='NBA'||analysis.game?.sport!=='NBA'||!analysis.game?.id?.startsWith('nba:espn:'))throw new ApiError('The saved record is not an NBA simulation.',422);return finishCloud(ctx,Response.json({analysis}));}

export async function readPublicNBA(id:string){if(!/^[a-f0-9]{64}$/.test(id))throw new ApiError('A public NBA analysis ID is required.',400);const saved=await sharedCache('analysis','nba-run:'+id);const analysis=saved?.data;if(!analysis||analysis.id!==id||analysis.result?.sport!=='NBA'||analysis.game?.sport!=='NBA')throw new ApiError('This public NBA simulation was not found. Your private saved records remain intact.',404);const board=await nbaMarkets().catch(()=>({items:[],diagnostic:{message:'Current sportsbook prices are unavailable.'}}));return{sport:'NBA',analysis,markets:compareNBAMarkets(analysis.result,board.items??[],analysis.game),marketDiagnostic:board.diagnostic??null,archived:true,modelValidated:false};}
