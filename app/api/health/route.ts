import {cloudOnlyDeployment,selectedBackend} from '@/lib/backend';
export const runtime='nodejs';
export const dynamic='force-dynamic';
type Check='reachable'|'unavailable'|'not_configured';
async function probe(url:URL,headers?:HeadersInit):Promise<Check>{
 try{const response=await fetch(url,{headers,signal:AbortSignal.timeout(5000),cache:'no-store'});if(!response.ok)return 'unavailable';const body=await response.json();return body?.status==='unconfigured'?'unavailable':'reachable';}catch{return 'unavailable';}
}
/** Public liveness exposes configuration booleans only. Deep readiness uses
 * server-held credentials and never reads or returns personal account rows. */
export async function GET(request:Request){
 const backend=selectedBackend(),configuration={supabase:Boolean(process.env.SUPABASE_URL&&process.env.SUPABASE_PUBLISHABLE_KEY),simulations:Boolean(process.env.SIMULATION_SERVICE_URL&&(process.env.SIMULATION_SERVICE_TOKEN?.length??0)>=32),assistant:Boolean(process.env.OPENAI_API_KEY)};
 const base={application:'GRIDIRON AI',version:'5.0.0',backend,cloudOnly:cloudOnlyDeployment(),configuration};
 if(new URL(request.url).searchParams.get('check')!=='dependencies')return Response.json({...base,status:'ok'},{headers:{'Cache-Control':'no-store'}});
 const checks:{supabase:Check;simulations:Check}={supabase:'not_configured',simulations:'not_configured'};
 await Promise.all([
  (async()=>{if(configuration.supabase){try{checks.supabase=await probe(new URL('/auth/v1/health',process.env.SUPABASE_URL),{apikey:process.env.SUPABASE_PUBLISHABLE_KEY!});}catch{checks.supabase='unavailable';}}})(),
  (async()=>{if(configuration.simulations){try{const url=new URL(process.env.SIMULATION_SERVICE_URL!);if(!['http:','https:'].includes(url.protocol))return;url.pathname=url.pathname.replace(/\/$/,'')+'/health';checks.simulations=await probe(url);}catch{checks.simulations='unavailable';}}})()
 ]);
 const ready=(backend!=='supabase'||checks.supabase==='reachable')&&checks.simulations==='reachable';
 return Response.json({...base,status:ready?'ready':'degraded',checks,limitations:'Reachability does not establish model calibration, a completed simulation, email delivery or a live AI response.'},{status:ready?200:503,headers:{'Cache-Control':'no-store'}});
}
