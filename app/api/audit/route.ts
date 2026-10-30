import {requireUser,errorResponse} from '@/lib/auth';
import {getDb} from '@/lib/db';
import {contractHistory} from '@/lib/contracts';
import {readInjuries} from '@/lib/injuries';
import {auditWorkspace} from '@/lib/auditor';
export const runtime='nodejs';export const dynamic='force-dynamic';
export async function GET(request:Request){try{const user=await requireUser(request),history=contractHistory(user.id),simulations=getDb().prepare('SELECT id,status,result,data,created_at FROM simulation_jobs WHERE user_id=? ORDER BY created_at DESC LIMIT 500').all(user.id) as Record<string,any>[];return Response.json(auditWorkspace({...history,injuries:readInjuries(user.id).history,simulations}),{headers:{'Cache-Control':'private,no-store'}});}catch(e){return errorResponse(e);}}
