import {handleCloudRequest} from '@/lib/cloud/handler';
export const runtime='nodejs';
export const dynamic='force-dynamic';
export const maxDuration=900;
type Context={params:Promise<{path:string[]}>};
async function handle(request:Request,context:Context){return handleCloudRequest(request,(await context.params).path);}
export {handle as GET,handle as POST,handle as PUT,handle as PATCH,handle as DELETE};
