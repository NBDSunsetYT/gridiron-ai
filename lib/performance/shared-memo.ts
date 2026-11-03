import {createHash} from 'node:crypto';
import {gzipSync,gunzipSync} from 'node:zlib';
import {cloudClient} from '../cloud/context';
import {ApiError} from '../auth';
import {performanceEvent,measure} from './metrics';
type Scope='cfb_prepare'|'market_board'|'auto_props'|'cfb_status'|'cfb_schedule';
type Options={ttlMs:number;leaseMs?:number;waitMs?:number;cacheWhen?:(v:any)=>boolean};
const memory=new Map<string,{expires:number;value:any;bytes:number}>(),pending=new Map<string,Promise<any>>();let bytes=0;
const hash=(value:string|Uint8Array)=>createHash('sha256').update(value).digest('hex');
// Only public research may enter this cache. Auth, Wallet, user preferences and
// conversations deliberately do not use it. Reuses existing cache/lease tables.
const prohibited=/"(?:user_id|userId|access_token|refresh_token|authorization|password|api_?key|service_role_key|bankroll|deposits|withdrawals)"\s*:/i;
export function packPublic(value:unknown){const raw=Buffer.from(JSON.stringify(value));if(raw.length>16_000_000||prohibited.test(raw.toString()))throw new Error('Public cache payload rejected');const compressed=gzipSync(raw,{level:1});if(compressed.length>500_000)throw new Error('Public cache payload bound exceeded');return{encoding:'gzip-base64-v1',body:compressed.toString('base64'),sha256:hash(raw),bytes:raw.length};}
export function unpackPublic(value:any){if(value?.encoding!=='gzip-base64-v1'||typeof value.body!=='string'||value.body.length>700_000||!Number.isSafeInteger(value.bytes)||value.bytes<0||value.bytes>16_000_000)throw new Error('Invalid public cache envelope');const raw=gunzipSync(Buffer.from(value.body,'base64'),{maxOutputLength:16_000_000});if(raw.length!==value.bytes||hash(raw)!==value.sha256||prohibited.test(raw.toString()))throw new Error('Public cache integrity failed');return JSON.parse(raw.toString());}
function remember(key:string,value:any,expires:number){const size=Buffer.byteLength(JSON.stringify(value));if(size>8_000_000)return;const old=memory.get(key);if(old){bytes-=old.bytes;memory.delete(key);}while(memory.size&&(memory.size>=40||bytes+size>16_000_000)){const first=memory.keys().next().value!;bytes-=memory.get(first)!.bytes;memory.delete(first);}memory.set(key,{value,expires,bytes:size});bytes+=size;}
export function sharedMemoEnabled(){return process.env.GRIDIRON_CLOUD_ONLY==='1'&&Boolean(process.env.SUPABASE_URL&&process.env.SUPABASE_PUBLISHABLE_KEY&&process.env.GRIDIRON_PUBLIC_INGEST_TOKEN);}
async function operation(payload:Record<string,unknown>){performanceEvent('database','cache_rpc');const {data,error}=await cloudClient().rpc('gridiron_performance_cache',{token:process.env.GRIDIRON_PUBLIC_INGEST_TOKEN,payload});if(error)throw new ApiError('Shared computation cache is temporarily unavailable. Existing research is preserved.',503);return data;}
/** Keys include the implementation and every input that affects the cached value.
 * Expired values never become fresh on failure. SQL generation fences late workers.
 * No probabilistic output is recomputed on a hit. */
export async function sharedPublicMemo<T>(scope:Scope,input:unknown,options:Options,work:()=>Promise<T>):Promise<T>{
 if(!sharedMemoEnabled())return work();
 const key=scope+':'+hash(JSON.stringify(input)),old=memory.get(key);if(old&&old.expires>Date.now()){performanceEvent(scope,'memory_hit');return structuredClone(old.value);}
 const active=pending.get(key);if(active){performanceEvent(scope,'single_flight');return structuredClone(await active);}
 const task=measure(scope,async()=>{const started=Date.now();let delay=200;
  for(;;){const state=await operation({action:'acquire',key,leaseMs:options.leaseMs??120000});
   if(state.state==='hit'){performanceEvent(scope,'shared_hit');const value=unpackPublic(state.value);remember(key,value,Date.parse(state.expiresAt));return value as T;}
   if(state.state==='claimed'){
    performanceEvent(scope,'miss');try{const value=await work();if(options.cacheWhen&&!options.cacheWhen(value)){await operation({action:'fail',key,generation:state.generation});return value;}
     const packed=packPublic(value),receipt=await operation({action:'finish',key,generation:state.generation,ttlMs:options.ttlMs,value:packed});if(receipt.accepted===true)remember(key,value,Date.parse(receipt.expiresAt));return value;
    }catch(error){await operation({action:'fail',key,generation:state.generation}).catch(()=>{});throw error;}
   }
   performanceEvent(scope,'lease_wait');if(Date.now()-started>= (options.waitMs??8000))throw new ApiError('Shared research preparation is already running or backing off. Results refresh automatically.',409);
   await new Promise(resolve=>setTimeout(resolve,delay));delay=Math.min(2000,Math.ceil(delay*1.8));
  }
 });pending.set(key,task);try{return structuredClone(await task);}finally{pending.delete(key);}
}
