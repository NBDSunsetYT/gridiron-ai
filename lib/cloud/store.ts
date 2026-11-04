import {randomUUID} from 'node:crypto';
import {ApiError} from '../auth';
import {cloudError,requireCloudUser,type CloudContext} from './context';
import {encodeCloudData,decodeCloudData} from './codec';
export type CloudRecord={id:string;kind:string;entity_key:string;data:Record<string,any>;source:string;observed_at:string;created_at:string;updated_at:string};
export function finiteJson(value:unknown,max=20_000_000){
 let raw:string|undefined;try{raw=JSON.stringify(value,(_k,v)=>{if(typeof v==='number'&&!Number.isFinite(v))throw Error();if(['bigint','function','symbol'].includes(typeof v))throw Error();return v;});}catch{throw new ApiError('Data must be finite JSON.');}
 if(raw===undefined||raw.length>max)throw new ApiError('Record data is missing or too large.');return JSON.parse(raw);
}
export async function records(ctx:CloudContext,kind:string,options:{entityKey?:string;limit?:number;dataKind?:string;dataStatus?:string;beforeUpdatedAt?:string;oldestFirst?:boolean}={}){
 const user=requireCloudUser(ctx),limit=Math.min(options.limit??5000,50000);if(!Number.isFinite(limit)||!Number.isInteger(limit)||limit<1)throw new ApiError('Invalid history limit.');const rows:CloudRecord[]=[];let offset=0,expected:number|null=null,bytes=0;
 for(;;){
  let query=ctx.client.from('gridiron_records').select('*',{count:'exact'}).eq('user_id',user.id).eq('kind',kind).order('created_at',{ascending:options.oldestFirst??false}).order('id',{ascending:options.oldestFirst??false}).range(offset,Math.min(offset+999,limit-1));if(options.entityKey!==undefined)query=query.eq('entity_key',options.entityKey);if(options.dataKind!==undefined)query=query.eq('data->>kind',options.dataKind);if(options.dataStatus!==undefined)query=query.eq('data->>status',options.dataStatus);if(options.beforeUpdatedAt!==undefined)query=query.lt('updated_at',options.beforeUpdatedAt);
  const {data,error,count}=await query;if(error)cloudError(error);
  if(typeof count!=='number')throw new ApiError('The research history count could not be verified. No partial history was returned.',503);
  if(expected===null)expected=count;else if(count!==expected)throw new ApiError('Research records changed during retrieval. Retry to load the current history.',409);
  const page=(data??[]).map(row=>({...row,data:decodeCloudData(row.data)})) as CloudRecord[];
  if(kind==='research_records/saved_simulation'){const{hydrateSavedNflData}=await import('../storage/saved-nfl');let expanded=0;for(let start=0;start<page.length;start+=4){const group=await Promise.all(page.slice(start,start+4).map(async row=>row.data.resultReference?{...row,data:await hydrateSavedNflData(row.data)}:row));expanded+=Buffer.byteLength(JSON.stringify(group));if(expanded>40_000_000)throw new ApiError('Expanded saved research exceeds the interactive request bound. Use a bounded query or project export; no partial history was returned.',413);page.splice(start,group.length,...group);}}
  bytes+=Buffer.byteLength(JSON.stringify(page),'utf8');
  if(bytes>40_000_000)throw new ApiError('Expanded research history exceeds this interactive request bound. Use a bounded query or project export; no partial history was returned.',413);
  rows.push(...page);offset+=page.length;const target=Math.min(expected,limit);
  if(offset===target)break;
  if(!page.length||offset>target)throw new ApiError('Research pagination could not reconcile the requested history. No partial history was returned.',409);
 }
 return rows;
}
/** Model performance must not silently cherry-pick the latest capped page. */
export async function allRecords(ctx:CloudContext,kind:string){
 const user=requireCloudUser(ctx),rows:CloudRecord[]=[];let offset=0,expected:number|null=null,bytes=0;
 for(;;){
  const{data,error,count}=await ctx.client.from('gridiron_records').select('*',{count:'exact'}).eq('user_id',user.id).eq('kind',kind).order('created_at',{ascending:false}).order('id',{ascending:false}).range(offset,offset+999);if(error)cloudError(error);
  if(typeof count!=='number')throw new ApiError('Complete research history could not be verified. No partial history was scored as the complete model record.',503);
  if(expected===null)expected=count;else if(count!==expected)throw new ApiError('Research records changed during retrieval. Retry before scoring the complete model history.',409);
  const page=(data??[]).map(row=>({...row,data:decodeCloudData(row.data)})) as CloudRecord[];
  if(kind==='research_records/saved_simulation'){const{hydrateSavedNflData}=await import('../storage/saved-nfl');let expanded=0;for(let start=0;start<page.length;start+=4){const group=await Promise.all(page.slice(start,start+4).map(async row=>row.data.resultReference?{...row,data:await hydrateSavedNflData(row.data)}:row));expanded+=Buffer.byteLength(JSON.stringify(group));if(expanded>40_000_000)throw new ApiError('Expanded saved research exceeds the interactive request bound. Use a bounded query or project export; no partial history was returned.',413);page.splice(start,group.length,...group);}}
  bytes+=Buffer.byteLength(JSON.stringify(page),'utf8');
  if(bytes>40_000_000)throw new ApiError('Complete expanded research history exceeds this interactive request bound. No partial history was scored as the complete model record; use a bounded report or project export.',413);
  rows.push(...page);offset+=page.length;
  if(offset===expected)break;
  if(!page.length||offset>expected)throw new ApiError('Research pagination could not reconcile every saved record. No partial history was scored as the complete model record.',409);
 }
 return rows;
}
export async function record(ctx:CloudContext,id:string,kind?:string){
 const user=requireCloudUser(ctx);let query=ctx.client.from('gridiron_records').select('*').eq('user_id',user.id).eq('id',id);if(kind)query=query.eq('kind',kind);
 const {data,error}=await query.maybeSingle();if(error)cloudError(error);if(!data)throw new ApiError('Owned record not found.',404);let value=decodeCloudData(data.data);if(data.kind==='research_records/saved_simulation'&&value.resultReference)value=await(await import('../storage/saved-nfl')).hydrateSavedNflData(value);return {...data,data:value} as CloudRecord;
}
export async function saveRecord(ctx:CloudContext,kind:string,data:Record<string,any>,options:{id?:string;entityKey?:string;source?:string;observedAt?:string}={}){
 const user=requireCloudUser(ctx),id=options.id??data.id??randomUUID(),now=new Date().toISOString();
 const normalized=finiteJson({...data,id}),encoded=['simulation_inputs','simulation_jobs','quant_runs'].includes(kind)?encodeCloudData(normalized):normalized;
 const row={id,user_id:user.id,kind,entity_key:options.entityKey??'',data:encoded,source:options.source??'user',observed_at:options.observedAt??now,version:String(data.modelVersion??data.version??'1'),created_at:data.createdAt??now,updated_at:now};
 const {error}=await ctx.client.from('gridiron_records').insert(row);if(error)cloudError(error);return{id,...data,createdAt:row.created_at};
}
export async function updateRecord(ctx:CloudContext,id:string,data:Record<string,any>){
 const user=requireCloudUser(ctx);const {data:rows,error}=await ctx.client.from('gridiron_records').update({data:encodeCloudData(finiteJson(data)),updated_at:new Date().toISOString()}).eq('user_id',user.id).eq('id',id).select('id');if(error)cloudError(error);if(!rows?.length)throw new ApiError('Owned mutable record not found.',404);
}
export async function deleteRecord(ctx:CloudContext,id:string){
 const user=requireCloudUser(ctx);const {data,error}=await ctx.client.from('gridiron_records').delete().eq('user_id',user.id).eq('id',id).select('id');if(error)cloudError(error);if(!data?.length)throw new ApiError('Owned record not found or historical record cannot be removed individually.',404);
}
export const unwrap=(rows:CloudRecord[]):Record<string,any>[]=>rows.map(r=>({...r.data,id:r.id,createdAt:r.created_at}));
export async function preferences(ctx:CloudContext){const user=requireCloudUser(ctx),{data,error}=await ctx.client.from('preferences').select('key,value').eq('user_id',user.id);if(error)cloudError(error);return Object.fromEntries((data??[]).map(r=>[r.key,r.value]));}
export async function updatePreferences(ctx:CloudContext,values:Record<string,any>){
 const user=requireCloudUser(ctx);if(!values||typeof values!=='object'||Array.isArray(values)||Object.keys(values).length>50)throw new ApiError('Provide at most 50 preference keys.');
 const rows=Object.entries(values).map(([key,value])=>{if(!/^[a-zA-Z0-9_.-]{1,80}$/.test(key))throw new ApiError('Invalid preference key.');return{user_id:user.id,key,value:finiteJson(value,100000),updated_at:new Date().toISOString()};});
 if(rows.length){const {error}=await ctx.client.from('preferences').upsert(rows,{onConflict:'user_id,key'});if(error)cloudError(error);}return preferences(ctx);
}
