import {cloudContext,finishCloud} from '@/lib/cloud/context';
import {errorResponse} from '@/lib/auth';
import {requireStorageAdmin,storageHealth} from '@/lib/storage/health';
export const runtime='nodejs';export const dynamic='force-dynamic';
export async function GET(request:Request){let ctx;try{ctx=await cloudContext(request);requireStorageAdmin(ctx);return finishCloud(ctx,Response.json(await storageHealth()));}catch(error){return finishCloud(ctx,errorResponse(error));}}
