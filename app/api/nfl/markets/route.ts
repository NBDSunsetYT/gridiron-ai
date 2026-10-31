import {handlePlayerProps} from '@/lib/player-props/handler';
export const runtime='nodejs';
export const dynamic='force-dynamic';
export const maxDuration=300;
export const GET=(request:Request)=>handlePlayerProps(request,[],'all');
