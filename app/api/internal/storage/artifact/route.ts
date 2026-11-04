import {timingSafeEqual,createHash} from 'node:crypto';
import {gunzipSync} from 'node:zlib';
import {ApiError,errorResponse} from '@/lib/auth';
import {PrivateR2Store,r2Configured} from '@/lib/storage/r2';
import {storageOperation} from '@/lib/storage/outbox';
export const runtime='nodejs';export const dynamic='force-dynamic';export const maxDuration=120;
const forbidden=/^(?:bankroll|ledger|deposits|withdrawals|wagers|settlements|accountBalance|password|email|authorization|cookie|api_key|access_token|refresh_token)$/i;
function safe(value:any,depth=0):boolean{if(depth>32)return false;if(Array.isArray(value))return value.every(v=>safe(v,depth+1));if(value&&typeof value==='object')return Object.entries(value).every(([key,v])=>!forbidden.test(key)&&safe(v,depth+1));return typeof value!=='number'||Number.isFinite(value);}
export async function POST(request:Request){try{
 const secret=process.env.SIMULATION_SERVICE_TOKEN,provided=request.headers.get('authorization')?.replace(/^Bearer /,'');if(!secret||secret.length<32||!provided||Buffer.byteLength(secret)!==Buffer.byteLength(provided)||!timingSafeEqual(Buffer.from(secret),Buffer.from(provided)))throw new ApiError('Private simulation-service authorization required.',401);
 if(process.env.GRIDIRON_ARCHIVE_MODEL_ARTIFACTS!=='1'||!r2Configured())throw new ApiError('Private model-artifact archival is not enabled.',503);
 const sport=request.headers.get('x-gridiron-sport'),expected=request.headers.get('x-gridiron-artifact-sha256');if(!['NFL','CFB'].includes(sport??'')||!/^[a-f0-9]{64}$/.test(expected??'')||request.headers.get('content-type')!=='application/gzip')throw new ApiError('A bounded, checksummed football artifact is required.');
 const chunks:Uint8Array[]=[];let size=0;if(!request.body)throw new ApiError('Artifact body required.');const reader=request.body.getReader();try{while(true){const item=await reader.read();if(item.done)break;size+=item.value.length;if(size>3_200_000)throw new ApiError('Compressed artifact exceeds its safe transport bound.',413);chunks.push(item.value);}}finally{await reader.cancel().catch(()=>{});}
 const raw=gunzipSync(Buffer.concat(chunks),{maxOutputLength:20_000_000});if(createHash('sha256').update(raw).digest('hex')!==expected)throw new ApiError('Artifact checksum mismatch.');const artifact=JSON.parse(raw.toString());if(!artifact||!Array.isArray(artifact.rows)||artifact.rows.length<1||artifact.rows.length>1_000_000||!artifact.sha256||!artifact.version||!safe(artifact)||artifact.rows.some((r:any)=>typeof r.game!=='string'||typeof r.o!=='string'||typeof r.d!=='string'))throw new ApiError('Only fitted football input artifacts may be archived here.');
 const reference=await new PrivateR2Store().put(raw,'artifacts',sport as 'NFL'|'CFB');await storageOperation({action:'archive_record',id:reference.sha256,sport,kind:'artifacts',reference});return Response.json({saved:true,reference},{headers:{'Cache-Control':'no-store'}});
 }catch(error){return errorResponse(error instanceof ApiError?error:new ApiError('Input artifact archival could not be verified. Existing research is preserved.',503));}}
