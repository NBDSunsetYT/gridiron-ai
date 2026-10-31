import {sportsDataBridgeConfiguration} from './sportsbook-reference/bridge';
import {footballStorage,persistProviderQuotes} from './college-football/store';
import {compareFreeProp} from './free-prop-comparison';
import {createHash} from 'node:crypto';
const hash=(v:unknown)=>createHash('sha256').update(JSON.stringify(v)).digest('hex');
export async function freeProps(sport:'NFL'|'CFB',cursor=0,analyze=false){
 const unavailable=(message:string)=>({sport,status:'unavailable',provider:null,items:[],totalResults:0,diagnostic:{message},primaryProvider:'PropLine',fallbackVerified:false});
 if(sportsDataBridgeConfiguration())return unavailable('The secure Render prop gateway is not connected.');
 const response=await fetch(new URL('/data/props/'+sport+'?cursor='+cursor+'&limit=500',process.env.GRIDIRON_RENDER_DATA_URL!),{headers:{Authorization:'Bearer '+process.env.GRIDIRON_DATA_BRIDGE_TOKEN},cache:'no-store',redirect:'error',signal:AbortSignal.timeout(55000)});
 if(Number(response.headers.get('content-length')??0)>4_000_000)throw Error('Response exceeds safe bound');
 const raw=await response.text();if(Buffer.byteLength(raw)>4_000_000||raw.includes(process.env.GRIDIRON_DATA_BRIDGE_TOKEN!))throw Error('Unsafe provider response');
 const value=JSON.parse(raw);if(!response.ok||value.sport!==sport||!Array.isArray(value.items)||value.items.length>500||value.items.some((r:any)=>r.provider!=='PropLine'||r.sport!==sport||r.dataFamily!=='sportsbook_reference'||r.draftKingsPredictionsEquivalent!==false||!Number.isSafeInteger(r.americanOdds)||Math.abs(r.americanOdds)<100||!Number.isFinite(Date.parse(r.sourceUpdatedAt))||Date.now()-Date.parse(r.sourceUpdatedAt)>300000||Date.parse(r.sourceUpdatedAt)>Date.now()+60000))throw Error('Unverified provider data');
 const analysisChecks:any[]=[];const modelStates=new Map<string,any>();const events=[...new Set<string>(value.items.map((r:any)=>r.espnEventId).filter((id:any)=>typeof id==='string'&&/^\d+$/.test(id)))].slice(0,analyze?1:0);
 for(const event of events){try{
  if(sport==='CFB'){
   const source=await import('./college-football/service');let detail=await source.collegeGameDetail('cfb:espn:'+event);
   if(analyze&&!detail.analysis&&detail.canAnalyze)detail=await source.analyzeCollegeGame(detail.game.id,10000);
   analysisChecks.push({eventId:event,ready:detail.canAnalyze,reason:detail.message,simulationId:detail.analysis?.id??null});if(detail.analysis?.result&&!detail.analysis.stale)modelStates.set(event,{result:detail.analysis.result,research:detail.analysis.research,stale:false,gameId:detail.game.id,analysisId:detail.analysis.id});
  }else{const source=await import('./public-nfl/service'),schedule=await source.loadSchedule(),game=schedule.games.find(g=>String(g.espnId)===event);if(game){const job=await(await import('./sportsbook-reference/service')).existingModel(game);if(!job&&analyze)await source.analyzePublicGame(game.id,10000);if(job?.result)modelStates.set(event,{result:job.result.result,research:job.result.research,stale:false,gameId:game.id,analysisId:job.id});}}
 }catch{analysisChecks.push({eventId:event,status:'unavailable',reason:'Current source evidence or compute capacity could not be verified. No substitute probability was supplied.'});}}
 value.items=value.items.map((row:any)=>{const state=modelStates.get(row.espnEventId),result=state?.result;let playerId:string|undefined;
  if(sport==='CFB'&&/^espn:\d+$/.test(row.player.id??''))playerId='cfb:'+row.player.id;
  if(sport==='NFL'&&result){const matches=(state.research?.playerCatalog??[]).filter((p:any)=>'espn:'+p.espnId===row.player.id);if(matches.length===1)playerId=matches[0].id;}
  const distribution=playerId?result?.players?.[playerId]?.[row.statistic]:null;
  const comparison=compareFreeProp(row,distribution?{sport,providerPlayerId:row.player.id,providerEventId:row.eventId,kickoff:result.eventStart,stale:state.stale,simulations:result.simulations,statistic:row.statistic,histogram:distribution.histogram,modelVersion:result.modelVersion}:null);
  return{...row,...comparison,marketImpliedProbability:row.americanOdds<0?Math.abs(row.americanOdds)/(100+Math.abs(row.americanOdds)):100/(100+row.americanOdds),modelGameId:state?.gameId??(sport==='CFB'&&row.espnEventId?'cfb:espn:'+row.espnEventId:null),simulationId:state?.analysisId??null,monteCarloStandardError:comparison.modelProbability===null?null:Math.sqrt(comparison.modelProbability*(1-comparison.modelProbability)/result.simulations),modelUncertainty:result?.uncertainty??null};});
 const storage=await footballStorage();let persistence:any={saved:false,status:storage.admissionAvailable===false?'paused_capacity':'not_saved',count:0,message:storage.message};
 if(storage.admissionAvailable===true){let saved=0;for(let at=0;at<value.items.length;at+=80){const rows=value.items.slice(at,at+80);const outcome=await persistProviderQuotes(rows.map((r:any)=>({id:hash([r.id,r.sourceUpdatedAt]),provider:'PropLine' as const,sport,marketFamily:'sportsbook_reference' as const,eventId:r.eventId,marketId:r.market,selection:r.player.id+':'+r.side,line:r.threshold,americanOdds:r.americanOdds,observedAt:r.observedAt,quotedAt:null,sourceUrl:r.sourceUrl,data:r})));if(!outcome.saved){persistence=outcome;break;}saved+=outcome.count;persistence={saved:true,status:'saved',count:saved};}}
 return{...value,persistence,analysisChecks,analysisScope:analyze?'One verified matchup per bounded request; remaining rows have no invented model estimate.':'Market discovery only. Request analysis to retrieve supported simulation evidence.',analysisComplete:false};
}
