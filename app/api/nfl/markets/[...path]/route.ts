import {handlePlayerProps} from '@/lib/player-props/handler';
export const runtime='nodejs';
export const dynamic='force-dynamic';
export const maxDuration=300;
async function handle(request:Request,context:{params:Promise<{path:string[]}>}){return handlePlayerProps(request,(await context.params).path,'all');}
export const GET=handle;
export const POST=handle;
