import {liveFootball} from '@/lib/live-football/service';
import {ApiError,errorResponse} from '@/lib/auth';
export const runtime='nodejs';export const dynamic='force-dynamic';
export async function GET(request:Request){try{const sport=new URL(request.url).searchParams.get('sport')??'NFL';if(sport!=='NFL'&&sport!=='CFB')throw new ApiError('Choose NFL or CFB.');return Response.json(await liveFootball(sport),{headers:{'Cache-Control':'no-store'}});}catch(e){return errorResponse(e);}}
