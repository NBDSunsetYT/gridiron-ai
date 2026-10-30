import {timingSafeEqual,createHash} from 'node:crypto';
import {NextResponse} from 'next/server';
import {getDb} from '@/lib/db';
import {requireUser,guardMutation,errorResponse,readJsonObject,rateLimit,ApiError} from '@/lib/auth';
import {processSimulationJobs} from '@/lib/jobs';
export const runtime='nodejs';
export const maxDuration=900;
function cronAuthorized(request:Request){const secret=process.env.CRON_SECRET;if(!secret||secret.length<32)return false;const supplied=request.headers.get('authorization')??'';return timingSafeEqual(createHash('sha256').update(supplied).digest(),createHash('sha256').update(`Bearer ${secret}`).digest());}
export async function GET(request:Request){try{const u=await requireUser(request);const jobs=(getDb().prepare("SELECT id,status,data,error,created_at,updated_at FROM simulation_jobs WHERE user_id=? AND kind='injury_resimulation' ORDER BY created_at DESC LIMIT 100").all(u.id) as any[]).map(r=>({id:r.id,status:r.status,data:JSON.parse(r.data),error:r.error,createdAt:r.created_at,updatedAt:r.updated_at}));return NextResponse.json({jobs,worker:{onInjurySave:true,recovery:'POST /api/jobs with operator CRON_SECRET or signed-in owner. Stale running leases can be recovered after 20 minutes.'}},{headers:{'Cache-Control':'private,no-store'}});}catch(e){return errorResponse(e);}}
export async function POST(request:Request){try{
  if(cronAuthorized(request))return NextResponse.json(await processSimulationJobs(undefined,1));
  guardMutation(request);const u=await requireUser(request);rateLimit(`jobs:${u.id}`,6,60000);const body=await readJsonObject(request);
  if(body.action==='retry'){
    if(typeof body.jobId!=='string')throw new ApiError('A job ID is required.');
    const changed=getDb().prepare("UPDATE simulation_jobs SET status='queued',error=NULL,updated_at=? WHERE id=? AND user_id=? AND kind='injury_resimulation' AND status='blocked'").run(new Date().toISOString(),body.jobId,u.id);
    if(!changed.changes)throw new ApiError('No blocked owned resimulation job was found.',404);
  }
  return NextResponse.json(await processSimulationJobs(u.id,1));
}catch(e){return errorResponse(e);}}
