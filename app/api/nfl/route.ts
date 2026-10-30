import {handlePublicNfl} from '@/lib/public-nfl/handler';
export const runtime='nodejs';
export const dynamic='force-dynamic';
export const maxDuration=300;
export const GET=(request:Request)=>handlePublicNfl(request);
