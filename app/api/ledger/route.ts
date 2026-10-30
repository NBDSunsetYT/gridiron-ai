import { errorResponse,readJsonObject,guardMutation,rateLimit,requireUser } from '@/lib/auth';
import {getLedger,postTransaction,reverseTransaction} from '@/lib/ledger';
export const runtime='nodejs'; export const dynamic='force-dynamic';
export async function GET(request:Request){try{const user=await requireUser(request);return Response.json(getLedger(user.id),{headers:{'Cache-Control':'no-store'}});}catch(e){return errorResponse(e);}}
export async function POST(request:Request){try{guardMutation(request);const user=await requireUser(request);rateLimit('ledger:'+user.id,60);return Response.json(postTransaction(user.id,await readJsonObject(request)),{status:201});}catch(e){return errorResponse(e);}}
export async function PUT(request:Request){try{guardMutation(request);const user=await requireUser(request);rateLimit('ledger:'+user.id,60);const body=await readJsonObject(request);return Response.json(reverseTransaction(user.id,String(body.id),String(body.note||'')));}catch(e){return errorResponse(e);}}
