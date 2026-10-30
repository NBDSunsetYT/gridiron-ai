import {errorResponse,guardMutation,requireUser} from '@/lib/auth';import {deleteResearchRecord,getResearchRecord} from '@/lib/research-store';
export const runtime='nodejs';export const dynamic='force-dynamic';type Context={params:Promise<{id:string}>};
export async function GET(request:Request,context:Context){try{const user=await requireUser(request);return Response.json({record:getResearchRecord(user.id,(await context.params).id)},{headers:{'Cache-Control':'no-store'}});}catch(e){return errorResponse(e);}}
export async function DELETE(request:Request,context:Context){try{guardMutation(request);const user=await requireUser(request);deleteResearchRecord(user.id,(await context.params).id);return Response.json({deleted:true});}catch(e){return errorResponse(e);}}
