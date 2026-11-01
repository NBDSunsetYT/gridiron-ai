import {guardMutation,errorResponse,readJsonObject,ApiError} from '@/lib/auth';
import {publicRateLimit,putCache,sharedCache} from '@/lib/public-nfl/store';
import {putResearchObject,readResearchObject} from '@/lib/public-nfl/objects';
import {createHash,randomUUID} from 'node:crypto';
export const runtime='nodejs';export const dynamic='force-dynamic';export const maxDuration=120;
/** Isolated operational canary. No caller chooses a record, payload, identity or table.
 * Never writes a financial record, prediction or a user's research workspace. */
export async function POST(request:Request){try{guardMutation(request);if(Object.keys(await readJsonObject(request)).length)throw new ApiError('The storage check accepts no user data.');await publicRateLimit(request,'research-storage-check',3,3600000);
 const key='isolated-storage-check-v10.2',nonce=randomUUID(),checks:string[]=[];
 const first={purpose:'Isolated shared storage canary; not NFL research or a user record',nonce,stage:'written',checkedAt:new Date().toISOString()},pointer=await putResearchObject(first),id=createHash('sha256').update(nonce).digest('hex');checks.push('private_object_write');
 const fetched=await readResearchObject(pointer);if(fetched.nonce!==nonce||fetched.stage!=='written')throw new ApiError('The isolated object read did not match.',502);checks.push('private_object_read');
 await putCache('status',key,pointer,id,3600000);checks.push('database_metadata_write');const written=await sharedCache('status',key);if(written?.data.nonce!==nonce)throw new ApiError('The isolated database write did not verify.',502);checks.push('database_metadata_read');
 const second={...first,stage:'updated'},next=await putResearchObject(second);await putCache('status',key,next,id,3600000);const updated=await sharedCache('status',key);if(updated?.data.nonce!==nonce||updated.data.stage!=='updated')throw new ApiError('The isolated update did not verify.',502);checks.push('database_metadata_update','updated_object_retrieval');if((await readResearchObject(pointer)).stage!=='written')throw new ApiError('The previous immutable payload changed.',502);checks.push('original_object_preserved');
 return Response.json({status:'passed',checks,privateUserRecordsTouched:false,financialWrites:false,tableReset:false,checkedAt:new Date().toISOString()},{headers:{'Cache-Control':'no-store'}});
 }catch(e){return errorResponse(e);}}
export async function GET(){try{const row=await sharedCache('status','isolated-storage-check-v10.2');return Response.json({status:row?.data.stage==='updated'?'verified_previous_canary':'not_tested',updatedAt:row?.updated_at??null,privateUserRecordsTouched:false},{headers:{'Cache-Control':'no-store'}});}catch(e){return errorResponse(e);}}
