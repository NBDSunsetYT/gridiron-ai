import {ApiError,errorResponse,readJsonObject,guardMutation,rateLimit,requireUser} from '@/lib/auth';
import {getLedger,placeBet,settleBet} from '@/lib/ledger';
export const runtime='nodejs';export const dynamic='force-dynamic';
export async function GET(request:Request){try{const user=await requireUser(request);return Response.json({bets:getLedger(user.id).bets},{headers:{'Cache-Control':'no-store'}});}catch(e){return errorResponse(e);}}
export async function POST(request:Request){try{guardMutation(request);const user=await requireUser(request);rateLimit('bets:'+user.id,60);const body=await readJsonObject(request);if(body.action==='place')return Response.json(placeBet(user.id,body),{status:201});if(body.action==='settle')return Response.json(settleBet(user.id,body));throw new ApiError('Unknown wager action.');}catch(e){return errorResponse(e);}}
