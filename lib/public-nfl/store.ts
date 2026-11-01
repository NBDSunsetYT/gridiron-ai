import {cloudClient} from '../cloud/context';
import {ApiError} from '../auth';
import {researchStorageFailure} from './storage-errors';
import {putResearchObject,readResearchObject,isResearchPointer,hydrateResearchJob} from './objects';

export type SharedCache={kind:string;key:string;data:Record<string,any>;input_hash:string|null;updated_at:string;expires_at:string|null};
export type SharedJob={id:string;game_id:string;input_hash:string;status:'queued'|'running'|'completed'|'failed';data:Record<string,any>;result:Record<string,any>|null;error:string|null;lease:string|null;created_at:string;updated_at:string};
const client=()=>cloudClient();
function failure(error:unknown):never{return researchStorageFailure(error);}
export async function sharedWrite(payload:Record<string,any>):Promise<any>{
 const token=process.env.GRIDIRON_PUBLIC_INGEST_TOKEN;if(!token||token.length<40)throw new ApiError('Automatic NFL research is temporarily unavailable. Please retry shortly.',503);
 let packed={...payload};
 if(payload.action==='job_enqueue'&&payload.data?.context&&Buffer.byteLength(JSON.stringify(payload.data.context))>8192)packed={...payload,data:{...payload.data,context:await putResearchObject(payload.data.context)}};
 if(payload.action==='job_complete'&&payload.result?.result){const pointer=payload.gameId?await(await import('../storage/research')).saveSharedResearch('NFL',payload.gameId,'simulation',payload.result):await putResearchObject(payload.result),r=payload.result.result;packed={...payload,result:{payload:pointer,result:Object.fromEntries(['modelVersion','simulations','home','away','homeWinProbability','awayWinProbability','tieProbability','eventStart'].filter(k=>r[k]!==undefined).map(k=>[k,r[k]])),summary:payload.result.summary?{generatedByAI:payload.result.summary.generatedByAI,method:payload.result.summary.method}:null}};}
 const result=await client().rpc('gridiron_public_write',{token,payload:packed});if(result.error)failure(result.error);return result.data?.game_id?hydrateResearchJob(result.data):result.data;
}
export async function sharedCache(kind:string,key:string):Promise<SharedCache|null>{
 const result=await client().from('shared_nfl_cache').select('*').eq('kind',kind).eq('key',key).maybeSingle();if(result.error)failure(result.error);const row=result.data;return row&&isResearchPointer(row.data)?{...row,data:await readResearchObject(row.data)}:row;
}
export async function putCache(kind:string,key:string,data:Record<string,any>,inputHash:string,ttlMs:number){return sharedWrite({action:'cache_put',kind,key,data,inputHash,expiresAt:new Date(Date.now()+ttlMs).toISOString()});}
export async function latestJob(gameId:string,inputHash?:string):Promise<SharedJob|null>{let query=client().from('shared_nfl_jobs').select('*').eq('game_id',gameId);if(inputHash)query=query.eq('input_hash',inputHash);const result=await query.order('created_at',{ascending:false}).limit(1).maybeSingle();if(result.error)failure(result.error);return hydrateResearchJob(result.data);}
export async function sharedJob(id:string):Promise<SharedJob|null>{const result=await client().from('shared_nfl_jobs').select('*').eq('id',id).maybeSingle();if(result.error)failure(result.error);return hydrateResearchJob(result.data);}
export async function cachedContextStates(gameIds:string[]):Promise<Map<string,SharedCache>>{
 const contexts=new Map<string,SharedCache>();for(let offset=0;offset<gameIds.length;offset+=35){const result=await client().from('shared_nfl_cache').select('kind,key,data,input_hash,updated_at,expires_at').eq('kind','detail').in('key',gameIds.slice(offset,offset+35));if(result.error)failure(result.error);for(const row of result.data??[])contexts.set(row.key,row as SharedCache);}return contexts;
}
export async function latestJobs(limit=100,inputHashes?:string[]):Promise<SharedJob[]>{
 // The home screen needs three probabilities, not every player's histogram or
 // original injury context for every archived job.
 const columns='id,game_id,input_hash,status,error,created_at,updated_at,requested_count:data->simulations,simulated_count:result->result->simulations,home_probability:result->result->homeWinProbability,away_probability:result->result->awayWinProbability,tie_probability:result->result->tieProbability,model_version:result->result->modelVersion';
 const rows:any[]=[];const groups=inputHashes?Array.from({length:Math.ceil(inputHashes.length/35)},(_,index)=>inputHashes.slice(index*35,index*35+35)):[undefined];
 for(const group of groups){let query=client().from('shared_nfl_jobs').select(columns);if(group)query=query.in('input_hash',group);const result=await query.order('created_at',{ascending:false}).limit(limit);if(result.error)failure(result.error);rows.push(...result.data??[]);}
 return rows.map((row:any)=>({id:row.id,game_id:row.game_id,input_hash:row.input_hash,status:row.status,error:row.error,lease:null,created_at:row.created_at,updated_at:row.updated_at,data:{simulations:row.requested_count},result:row.status==='completed'?{result:{simulations:row.simulated_count,homeWinProbability:row.home_probability,awayWinProbability:row.away_probability,tieProbability:row.tie_probability,modelVersion:row.model_version}}:null}));
}
export function fresh(cache:SharedCache|null){return Boolean(cache&&cache.expires_at&&Date.parse(cache.expires_at)>Date.now());}
export async function publicRateLimit(request:Request,action:string,limit=12,windowMs=3600000){
 const {createHash}=await import('node:crypto');
 // Only a one-way bounded client identifier is retained; no IP or account data
 // enters a public research record or browser response.
 const ip=request.headers.get('x-real-ip')||request.headers.get('x-forwarded-for')?.split(',')[0]?.trim()||'unknown';
 const key=createHash('sha256').update(action+'\0'+ip).digest('hex');
 const result=await sharedWrite({action:'rate_limit',key,limit,windowMs});if(!result?.allowed)throw new ApiError('Research requests are temporarily limited. Please try again later; saved results remain available.',429);
}
