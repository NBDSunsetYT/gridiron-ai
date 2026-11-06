import {computeAllowed} from '@/lib/compute/policy';
import {version} from '@/package.json';
import {cloudOnlyDeployment,selectedBackend} from '@/lib/backend';
export const runtime='nodejs';
export const dynamic='force-dynamic';
type Check='reachable'|'unavailable'|'not_configured'|'queued_only';
async function probe(url:URL,headers?:HeadersInit):Promise<Check>{
 try{const response=await fetch(url,{headers,signal:AbortSignal.timeout(5000),cache:'no-store'});if(!response.ok)return 'unavailable';const body=await response.json();return body?.status==='unconfigured'?'unavailable':'reachable';}catch{return 'unavailable';}
}
/** Public liveness exposes configuration booleans only. Deep readiness uses
 * server-held credentials and never reads or returns personal account rows. */
export async function GET(request:Request){
 const backend=selectedBackend(),provider=process.env.AI_PROVIDER?.trim()||'openai',supportedProvider=provider==='openai'||provider==='vercel-gateway',assistantConfigured=provider==='openai'?Boolean(process.env.OPENAI_API_KEY):provider==='vercel-gateway'?Boolean(process.env.AI_GATEWAY_API_KEY||process.env.VERCEL_OIDC_TOKEN):false;
 const configuration={supabase:Boolean(process.env.SUPABASE_URL&&process.env.SUPABASE_PUBLISHABLE_KEY),simulations:Boolean(process.env.SIMULATION_SERVICE_URL&&(process.env.SIMULATION_SERVICE_TOKEN?.length??0)>=32),assistant:assistantConfigured};
 // Credential presence is configuration, never a credit, entitlement or live
 // generation check. Provider budget/status probes remain private operations.
 const assistantStatus={provider:supportedProvider?provider:'unsupported',credentialConfigured:assistantConfigured,generationVerified:false,status:!supportedProvider?'invalid_provider':assistantConfigured?'configured_unverified':'missing_credentials'};
 const commit=process.env.RENDER_GIT_COMMIT,branch=process.env.RENDER_GIT_BRANCH;
 const deployment={platform:process.env.RENDER==='true'?'render':process.env.VERCEL==='1'?'vercel':'local',commit:commit&&/^[a-f0-9]{40}$/.test(commit)?commit:null,branch:branch&&/^[A-Za-z0-9/._-]{1,150}$/.test(branch)?branch:null};
 const base={application:'GRIDIRON AI',version,backend,cloudOnly:cloudOnlyDeployment(),configuration,assistantStatus,deployment,computeMode:computeAllowed()?'worker_or_local':'cache_and_queue_only',workerExecutionVerified:false};
 if(new URL(request.url).searchParams.get('check')!=='dependencies')return Response.json({...base,status:'ok'},{headers:{'Cache-Control':'no-store'}});
 const checks:{supabase:Check;simulations:Check}={supabase:'not_configured',simulations:'not_configured'};
 await Promise.all([
  (async()=>{if(configuration.supabase){try{checks.supabase=await probe(new URL('/auth/v1/health',process.env.SUPABASE_URL),{apikey:process.env.SUPABASE_PUBLISHABLE_KEY!});}catch{checks.supabase='unavailable';}}})(),
  (async()=>{if(!computeAllowed()){checks.simulations='queued_only';return;}if(configuration.simulations){try{const url=new URL(process.env.SIMULATION_SERVICE_URL!);if(!['http:','https:'].includes(url.protocol))return;url.pathname=url.pathname.replace(/\/$/,'')+'/health';checks.simulations=await probe(url);}catch{checks.simulations='unavailable';}}})()
 ]);
 const ready=(backend!=='supabase'||checks.supabase==='reachable')&&(checks.simulations==='reachable'||checks.simulations==='queued_only');
 return Response.json({...base,status:ready?'ready':'degraded',checks,limitations:'Reachability and provider credential presence do not establish model calibration, a completed simulation, email delivery, AI credit entitlement or a live AI response.'},{status:ready?200:503,headers:{'Cache-Control':'no-store'}});
}
