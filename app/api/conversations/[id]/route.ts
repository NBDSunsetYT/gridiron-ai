import {errorResponse,readJsonObject,guardMutation,rateLimit,requireUser} from '@/lib/auth';
import {appendMessage,deleteConversation,getConversation,renameConversation} from '@/lib/research-store';
export const runtime='nodejs';export const dynamic='force-dynamic';
type Context={params:Promise<{id:string}>};
export async function GET(request:Request,context:Context){try{const user=await requireUser(request);return Response.json({conversation:getConversation(user.id,(await context.params).id)},{headers:{'Cache-Control':'no-store'}});}catch(e){return errorResponse(e);}}
export async function POST(request:Request,context:Context){try{guardMutation(request);const user=await requireUser(request);rateLimit('messages:'+user.id,60);const body=await readJsonObject(request);return Response.json({message:appendMessage(user.id,(await context.params).id,{role:body.role,content:body.content,data:body.data})},{status:201});}catch(e){return errorResponse(e);}}
export async function PATCH(request:Request,context:Context){try{guardMutation(request);const user=await requireUser(request);const body=await readJsonObject(request);return Response.json({conversation:renameConversation(user.id,(await context.params).id,body.title)});}catch(e){return errorResponse(e);}}
export async function DELETE(request:Request,context:Context){try{guardMutation(request);const user=await requireUser(request);deleteConversation(user.id,(await context.params).id);return Response.json({deleted:true});}catch(e){return errorResponse(e);}}
