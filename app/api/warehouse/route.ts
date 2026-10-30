import {requireUser,rateLimit,errorResponse} from '@/lib/auth';
import {handleWarehouse} from '@/lib/warehouse';
export const runtime='nodejs';export const dynamic='force-dynamic';
async function route(request:Request){try{const user=await requireUser(request);if(request.method!=='GET')rateLimit('warehouse:'+user.id,8,3600000);return await handleWarehouse(request,user.id);}catch(e){return errorResponse(e);}}
export const GET=route;export const POST=route;
