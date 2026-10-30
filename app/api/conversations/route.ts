import {errorResponse,readJsonObject,guardMutation,rateLimit,requireUser} from '@/lib/auth';
import {createConversation,listConversations} from '@/lib/research-store';
export const runtime='nodejs';export const dynamic='force-dynamic';
export async function GET(request:Request){try{const user=await requireUser(request);return Response.json({conversations:listConversations(user.id)},{headers:{'Cache-Control':'no-store'}});}catch(e){return errorResponse(e);}}
export async function POST(request:Request){try{guardMutation(request);const user=await requireUser(request);rateLimit('conversations:'+user.id,30);const body=await readJsonObject(request);return Response.json({conversation:createConversation(user.id,body.title)},{status:201});}catch(e){return errorResponse(e);}}
