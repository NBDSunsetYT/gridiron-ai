import {timingSafeEqual} from 'node:crypto';
import {cloudContext,finishCloud} from '@/lib/cloud/context';
import {ApiError,errorResponse,guardMutation,readJsonObject} from '@/lib/auth';
import {requireStorageAdmin} from '@/lib/storage/health';
import {deliverResearchQueue} from '@/lib/storage/outbox';
export const runtime='nodejs';export const dynamic='force-dynamic';export const maxDuration=120;
function scheduler(request:Request){const secret=process.env.CRON_SECRET,actual=request.headers.get('authorization')?.replace(/^Bearer /,'');return Boolean(secret&&secret.length>=32&&actual&&Buffer.byteLength(secret)===Buffer.byteLength(actual)&&timingSafeEqual(Buffer.from(secret),Buffer.from(actual)));}
export async function POST(request:Request){let ctx;try{if(!scheduler(request)){guardMutation(request);ctx=await cloudContext(request);requireStorageAdmin(ctx);}if(Object.keys(await readJsonObject(request)).length)throw new ApiError('Storage synchronization accepts no user payload.');return finishCloud(ctx,Response.json(await deliverResearchQueue(5)));}catch(error){return finishCloud(ctx,errorResponse(error));}}
