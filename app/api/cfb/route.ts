import {handleCollegeFootball} from '@/lib/college-football/handler';
export const runtime='nodejs';
export const dynamic='force-dynamic';
export const maxDuration=300;
export const GET=(request:Request)=>handleCollegeFootball(request);
