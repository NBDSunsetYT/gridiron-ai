import {createHash,randomUUID} from 'node:crypto';
import {getCache} from '@vercel/functions';
import {ApiError} from '../auth';
import {verifiedProbabilityInputs} from '../public-nfl/service';
import {footballWrite} from '../college-football/store';
const memory=new Map<string,{until:number;value:any}>(),running=new Map<string,Promise<any>>();
/** Temporary public evidence when shared PostgreSQL research admission is paused.
 * Uses the existing NFL engine and fenced daily budget; no user data enters this cache.
 * This cache never claims to be permanent personal history. */
export async function nflProbabilityBaseline(gameId:string,count:number){
 if(![10000,50000,100000].includes(count))throw new ApiError('Unsupported complete-game count.');
 const inputs=await verifiedProbabilityInputs(gameId,count),key=createHash('sha256').update(JSON.stringify(['nfl-probability-baseline-10.2',inputs.inputHash])).digest('hex'),old=memory.get(key);if(old&&old.until>Date.now())return old.value;
 const regional=process.env.VERCEL==='1'?getCache({namespace:'gridiron-nfl-probability-v10-2'}):null;
 const validate=(value:any)=>{const r=value?.result;return value?.sourceHash===inputs.inputHash&&value.until>Date.now()&&r?.simulations===count&&r.home===inputs.game.home&&r.away===inputs.game.away&&Date.parse(r.eventStart)===Date.parse(inputs.game.startTime)&&Date.parse(inputs.game.startTime)>Date.now()&&[r.home,r.away].every(team=>Array.isArray(r.scoreDistributions?.[team]?.histogram)&&r.scoreDistributions[team].histogram.every((b:any)=>Number.isFinite(b.value)&&Number.isSafeInteger(b.count)&&b.count>=0)&&r.scoreDistributions[team].histogram.reduce((s:number,b:any)=>s+b.count,0)===count);};
 try{const stored=await regional?.get(key);if(validate(stored))return (stored as any).value;}catch{}
 if(running.has(key))return running.get(key);const task=(async()=>{const endpoint=process.env.SIMULATION_SERVICE_URL,token=process.env.SIMULATION_SERVICE_TOKEN;if(!endpoint||!token||token.length<32)throw new ApiError('The private NFL worker is unavailable.',503);
 const lease=randomUUID(),reservation=await footballWrite({action:'reserve_compute',inputHash:key,simulations:count,lease});if(reservation.execute!==true)throw new ApiError('This complete-game analysis is running or its temporary cache expired. Check saved personal research before requesting more computation.',409);
 try{const response=await fetch(new URL('public/analyze',endpoint.endsWith('/')?endpoint:endpoint+'/'),{method:'POST',headers:{Authorization:'Bearer '+token,'Content-Type':'application/json'},body:JSON.stringify({game:inputs.game,inputContext:inputs.inputContext,simulations:count,seed:2026}),cache:'no-store',signal:AbortSignal.timeout(240000)});if(!response.ok)throw new ApiError('Current NFL evidence or the worker could not support this analysis. No forecast was substituted.',503);const payload=await response.json(),r=payload.result;
 const resultFields=['modelVersion','engineVersion','inputDataVersion','provenance','eventStart','evidenceCutoff','simulations','seed','home','away','homeWinProbability','awayWinProbability','tieProbability','scoreDistributions','totalDistribution','marginDistribution','players','contracts','jointOutcomes','convergence','uncertainty','createdAt','limitations'];
 const researchFields=['sources','playerCatalog','availability','injuryImpact','weatherImpact','playerNames','training'];
 const value={id:key,result:Object.fromEntries(resultFields.filter(k=>r?.[k]!==undefined).map(k=>[k,r[k]])),research:Object.fromEntries(researchFields.filter(k=>payload.research?.[k]!==undefined).map(k=>[k,payload.research[k]])),inputVersion:inputs.inputHash,persistent:false};
 const until=Math.min(Date.now()+30*60000,Date.parse(inputs.game.startTime)),entry={until,sourceHash:inputs.inputHash,value,result:value.result};if(!validate(entry))throw new ApiError('The complete NFL games did not reconcile with the verified matchup.',502);
 if(memory.size>=8)memory.delete(memory.keys().next().value!);memory.set(key,{until,value});try{if(Buffer.byteLength(JSON.stringify(entry))<2_000_000)await regional?.set(key,entry,{ttl:Math.max(1,Math.floor((until-Date.now())/1000)),tags:['public-nfl-probability']});}catch{}
 await footballWrite({action:'complete_compute',id:reservation.id,lease}).catch(()=>{});return value;
 }catch(e){await footballWrite({action:'fail_compute',id:reservation.id,lease}).catch(()=>{});throw e;}})();running.set(key,task);try{return await task;}finally{running.delete(key);}
}
