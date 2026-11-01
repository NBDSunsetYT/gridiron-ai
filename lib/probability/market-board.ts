import {createHash} from 'node:crypto';
import {ApiError} from '../auth';
import {sharedCache,putCache} from '../public-nfl/store';
import {putResearchObject} from '../public-nfl/objects';
const cacheKey=(sport:string,cursor:number)=>'last-propline-board:'+sport+':'+cursor;
/** Last verified definitions can support independent statistical research. Their
 * historical quotes are never revalidated as executable/current prices. */
export async function saveVerifiedPropBoard(sport:'NFL'|'CFB',cursor:number,value:any){
 if(value.sport!==sport||!Array.isArray(value.items)||!value.items.length||value.items.length>500||value.items.some((r:any)=>r.sport!==sport||r.provider!=='PropLine'||r.dataFamily!=='sportsbook_reference'||r.draftKingsPredictionsEquivalent!==false||!Number.isFinite(Date.parse(r.sourceUpdatedAt))))throw new ApiError('A verified provider board is required.',502);
 const pointer=await putResearchObject({...value,definitionArchiveObservedAt:value.checkedAt??new Date().toISOString()}),hash=createHash('sha256').update(JSON.stringify(pointer)).digest('hex');await putCache('status',cacheKey(sport,cursor),pointer,hash,24*3600000);
}
async function previous(sport:'NFL'|'CFB',cursor:number,current:any){
 try{const row=await sharedCache('status',cacheKey(sport,cursor)),v=row?.data;if(!v||v.sport!==sport||!Array.isArray(v.items)||!Number.isFinite(Date.parse(v.definitionArchiveObservedAt))||Date.now()-Date.parse(v.definitionArchiveObservedAt)>24*3600000)return null;
 const items=v.items.filter((r:any)=>r.provider==='PropLine'&&r.sport===sport&&Date.parse(r.kickoff)>Date.now()).map((r:any)=>({...r,marketCurrent:false}));if(!items.length)return null;
 return{...v,status:'partial',items,totalResults:items.length,nextCursor:null,liveMarketAvailable:false,currentSourceChecks:current?.sourceChecks??[],currentSourceDiagnostic:current?.diagnostic??null,diagnostic:{code:'historical_definitions_only',message:'Live prices are delayed or unavailable. These are previously verified definitions and historical quoted prices. Independent threshold research can continue; current break-even and after-fee value are unavailable.'}};
 }catch{return null;}
}
const boardCache=new Map<string,{until:number;promise:Promise<any>}>();
export async function loadPropBoard(sport:'NFL'|'CFB',cursor:number){
 if(process.env.NODE_ENV==='test')return fetchPropBoard(sport,cursor);
 const key=sport+':'+cursor,old=boardCache.get(key);if(old&&old.until>Date.now())return structuredClone(await old.promise);
 const promise=fetchPropBoard(sport,cursor);if(boardCache.size>=12)boardCache.delete(boardCache.keys().next().value!);boardCache.set(key,{until:Date.now()+20000,promise});try{return structuredClone(await promise);}catch(e){boardCache.delete(key);throw e;}
}
async function fetchPropBoard(sport:'NFL'|'CFB',cursor:number){
 let value:any;
 try{
  const response=await fetch(new URL('/data/props/'+sport+'?cursor='+cursor+'&limit=500',process.env.GRIDIRON_RENDER_DATA_URL!),{headers:{Authorization:'Bearer '+process.env.GRIDIRON_DATA_BRIDGE_TOKEN},cache:'no-store',redirect:'error',signal:AbortSignal.timeout(55000)});
  if(Number(response.headers.get('content-length')??0)>4_000_000)throw new ApiError('The provider board exceeded its response bound.',502);const raw=await response.text();if(Buffer.byteLength(raw)>4_000_000||raw.includes(process.env.GRIDIRON_DATA_BRIDGE_TOKEN!))throw new ApiError('An unsafe provider response was withheld.',502);
  value=JSON.parse(raw);if(!response.ok||value.sport!==sport||!Array.isArray(value.items)||value.items.length>500||value.items.some((r:any)=>r.provider!=='PropLine'||r.sport!==sport||r.dataFamily!=='sportsbook_reference'||r.draftKingsPredictionsEquivalent!==false||!Number.isSafeInteger(r.americanOdds)||Math.abs(r.americanOdds)<100||!Number.isFinite(Date.parse(r.sourceUpdatedAt))||Date.now()-Date.parse(r.sourceUpdatedAt)>300000||Date.parse(r.sourceUpdatedAt)>Date.now()+60000))throw new ApiError('The provider did not supply a verified current board.',503);
  if(value.items.length){await saveVerifiedPropBoard(sport,cursor,value).catch(()=>{});return{...value,liveMarketAvailable:true,items:value.items.map((r:any)=>({...r,marketCurrent:true}))};}
 }catch(error){const old=await previous(sport,cursor,null);if(old)return old;throw error;}
 return await previous(sport,cursor,value)??value;
}
