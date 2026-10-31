import {handleSportsbookReference} from '@/lib/sportsbook-reference/handler';
export const runtime='nodejs';export const dynamic='force-dynamic';export const maxDuration=300;
async function handle(request:Request,context:{params:Promise<{path:string[]}>}){return handleSportsbookReference(request,(await context.params).path);}
export const GET=handle;export const POST=handle;
