import {ApiError} from '../auth';
import {type CloudContext,requireCloudUser} from './context';
import {record} from './store';
import {after} from 'next/server';

export function backgroundSimulations(){return ['1','true'].includes(process.env.GRIDIRON_ASYNC_SIMULATIONS??'');}
type DispatchReceipt={accepted:boolean;scheduled?:boolean;message?:string};
/** The input is already durable before dispatch. A cold or unavailable worker
 * leaves the job queued; no timeout is presented as a completed simulation. */
export async function dispatchCloudSimulation(ctx:CloudContext,jobId:string):Promise<DispatchReceipt>{
 requireCloudUser(ctx);if(!ctx.accessToken)throw new ApiError('A verified account session is required to dispatch research.',401);
 const endpoint=process.env.SIMULATION_SERVICE_URL,secret=process.env.SIMULATION_SERVICE_TOKEN;
 if(!endpoint||!secret||secret.length<32)throw new ApiError('The private background simulation service is not configured.',503);
 const base=new URL(endpoint.endsWith('/')?endpoint:endpoint+'/');if(!['http:','https:'].includes(base.protocol))throw new ApiError('Invalid worker endpoint.',503);
 const execute=async(timeout:number)=>{try{
  const response=await fetch(new URL('jobs',base),{method:'POST',headers:{Authorization:`Bearer ${secret}`,'Content-Type':'application/json'},body:JSON.stringify({jobId,accessToken:ctx.accessToken}),signal:AbortSignal.timeout(timeout),cache:'no-store'});
  if(response.ok)return{accepted:true};
  return{accepted:false,message:response.status===429?'The single research worker is busy; this saved job remains queued.':'The worker did not accept this dispatch. Saved inputs remain available for retry.'};
 }catch{return{accepted:false,message:'The worker is starting or unavailable. This job and its complete inputs remain queued in Supabase.'};}};
 // A Vercel-hosted Python request cannot leave a daemon thread behind after its
 // response. Keep both invocations alive with Next's supported request lifecycle
 // while the UI receives its durable queued receipt immediately.
 if(process.env.GRIDIRON_WORKER_REQUEST_LIFETIME==='1'){
  after(async()=>{await execute(260000);});
  return{accepted:false,scheduled:true,message:'The saved job was scheduled within the server request lifecycle; inspect its persisted state for completion.'};
 }
 return execute(15000);
}
export async function resumeCloudSimulation(ctx:CloudContext,job:Record<string,any>){
 if(!backgroundSimulations()||job.data?.execution!=='background'||!['fit','simulate'].includes(job.kind))return job;
 if(job.status==='running'&&Date.parse(job.updatedAt)<Date.now()-20*60000){
  const next={...job,status:'queued',updatedAt:new Date().toISOString(),error:'The previous worker lease expired. The original inputs were retained for an authenticated retry.'};
  const u=requireCloudUser(ctx),changed=await ctx.client.from('gridiron_records').update({data:next,updated_at:next.updatedAt}).eq('user_id',u.id).eq('id',job.id).eq('kind','simulation_jobs').eq('data->>status','running').lt('updated_at',new Date(Date.now()-20*60000).toISOString()).select('id');
  if(changed.error)throw new ApiError('Worker recovery could not be confirmed. Previous research records were preserved.',503);
  job=changed.data?.length?next:(await record(ctx,job.id,'simulation_jobs')).data;
 }
 if(job.status==='queued')await dispatchCloudSimulation(ctx,job.id);
 return(await record(ctx,job.id,'simulation_jobs')).data;
}
