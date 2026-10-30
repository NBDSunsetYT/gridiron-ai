import {createHash,randomUUID} from 'node:crypto';
import {z} from 'zod';
import {ApiError,guardMutation,readJsonObject,requestOrigin} from './auth';
export const pipelineConfigSchema=z.object({enabled:z.boolean().default(false),intervalMinutes:z.union([z.literal(5),z.literal(15),z.literal(60)]).default(15),scheduleSync:z.boolean().default(false),oddsRefresh:z.boolean().default(false),injuryJobs:z.boolean().default(true),modelAudit:z.boolean().default(true),seasonFrom:z.number().int().min(1999).max(2200).default(new Date().getUTCFullYear()),seasonTo:z.number().int().min(1999).max(2200).default(new Date().getUTCFullYear())}).refine(p=>p.seasonTo>=p.seasonFrom&&p.seasonTo-p.seasonFrom<=2,'Choose at most three consecutive seasons.');
export type PipelineConfig=z.infer<typeof pipelineConfigSchema>;
export type PipelineRun={id:string;startedAt:string;completedAt?:string;status:'running'|'completed'|'partial'|'failed';steps:Record<string,any>[];sourcePolicy:string};
export type PipelineStorage={preferences:()=>Promise<Record<string,any>>;setPreference:(key:string,value:unknown)=>Promise<void>;history:(limit:number)=>Promise<Record<string,any>[]>;saveRun:(run:PipelineRun)=>Promise<void>;claimRun?:(run:PipelineRun)=>Promise<boolean>};
const active=new Set<string>();
const defaults=()=>pipelineConfigSchema.parse({});
function parsedConfig(value:unknown){const result=pipelineConfigSchema.safeParse(value);return result.success?result.data:defaults();}
/** Stable data comparison preserves entity IDs and values; observation/check clock metadata is not a new statistical feature. */
export function evidenceFingerprint(value:unknown){
 const stable=(input:any):any=>Array.isArray(input)?input.map(stable):input&&typeof input==='object'?Object.fromEntries(Object.keys(input).sort().filter(k=>!['checkedAt','auditedAt','lastCheckedAt','fetchedAt','requestId'].includes(k)).map(k=>[k,stable(input[k])])):input;
 return createHash('sha256').update(JSON.stringify(stable(value))).digest('hex');
}
export function pipelineDue(config:PipelineConfig,state:Record<string,any>|undefined,now=Date.now()){
 if(!config.enabled)return{due:false,nextRunAt:null,reason:'disabled'};
 const last=Date.parse(state?.lastStartedAt||'');const next=Number.isFinite(last)?last+config.intervalMinutes*60000:now;
 return{due:now>=next,nextRunAt:new Date(next).toISOString(),reason:now>=next?'due':'interval_not_elapsed'};
}
export async function handlePipeline(request:Request,userId:string,storage:PipelineStorage){
 const preferences=await storage.preferences(),config=parsedConfig(preferences.research_pipeline),state=preferences.research_pipeline_state;
 if(request.method==='GET')return Response.json({config,runs:await storage.history(30),status:{...pipelineDue(config,state),lastStartedAt:state?.lastStartedAt??null,lastCompletedAt:state?.lastCompletedAt??null,execution:'Browser scheduling runs while this app is open and visible. A separate owner-authenticated operator scheduler is required while closed.',sources:'No licensed live injury/news/weather source is implied by enabling this pipeline.'}},{headers:{'Cache-Control':'private,no-store'}});
 guardMutation(request);const input=await readJsonObject(request);
 if(input.action==='configure'){
  const value=pipelineConfigSchema.parse(input.config);if(value.seasonTo>new Date().getUTCFullYear()+1)throw new ApiError('A future unannounced season is not supported.');
  await storage.setPreference('research_pipeline',value);return Response.json({config:value,message:'Your pipeline preferences were saved. No external scheduler or notification subscription was created.'});
 }
 if(input.action!=='run')throw new ApiError('Choose configure or run.');
 const now=Date.now(),due=pipelineDue(config,state,now),last=Date.parse(state?.lastStartedAt||'');
 if(!config.enabled)return Response.json({skipped:true,...due,reason:'disabled'});
 if(active.has(userId))return Response.json({skipped:true,reason:'owned_run_in_progress'});
 if(Number.isFinite(last)&&now-last<60000)return Response.json({skipped:true,reason:'minimum_one_minute_cooldown',nextRunAt:new Date(last+60000).toISOString()});
 if(!due.due&&input.force!==true)return Response.json({skipped:true,...due});
 const run:PipelineRun={id:randomUUID(),startedAt:new Date(now).toISOString(),status:'running',steps:[],sourcePolicy:'Only configured authorized odds, explicit public schedule ingestion, saved injury evidence and owned queued jobs are consulted. Missing feeds remain unavailable.'};
 active.add(userId);
 try{
  if(storage.claimRun&&!await storage.claimRun(run))return Response.json({skipped:true,reason:'owned_run_already_claimed'});
  await storage.setPreference('research_pipeline_state',{...state,lastStartedAt:run.startedAt});
  const fingerprints={...(state?.fingerprints||{})};
  const call=async(path:string,body?:unknown)=>{
   const headers:Record<string,string>={cookie:request.headers.get('cookie')||'',origin:requestOrigin(request)};if(body)headers['content-type']='application/json';
   const response=await fetch(new URL(path,requestOrigin(request)),{method:body?'POST':'GET',headers,body:body?JSON.stringify(body):undefined,cache:'no-store',signal:AbortSignal.timeout(path==='/api/jobs'?850000:90000)});
   const raw=await response.text();let data:any;try{data=JSON.parse(raw);}catch{throw new ApiError('The owned source returned an invalid response.',502);}
   if(!response.ok)throw new ApiError(data.error||`Source request failed (${response.status}).`,response.status);return data;
  };
  const step=async(name:string,work:()=>Promise<unknown>)=>{const checkedAt=new Date().toISOString();try{const evidence=await work(),fingerprint=evidenceFingerprint(evidence),unchanged=fingerprints[name]===fingerprint;fingerprints[name]=fingerprint;run.steps.push({name,status:unchanged?'unchanged':'completed',checkedAt,fingerprint});}catch(error){run.steps.push({name,status:error instanceof ApiError&&[401,403,503,501].includes(error.status)?'unavailable':'failed',checkedAt,message:error instanceof ApiError?error.message:'Source could not be verified.'});}};
  if(config.scheduleSync)await step('public_schedule',()=>call('/api/warehouse',{action:'sync_games',seasonFrom:config.seasonFrom,seasonTo:config.seasonTo}));
  if(config.oddsRefresh)await step('authorized_odds',()=>call('/api/markets',{action:'refresh'}));
  if(config.injuryJobs)await step('injury_research_jobs',async()=>{
   const evidence=await call('/api/injuries'),queue=await call('/api/jobs'),queued=(queue.jobs||[]).filter((j:any)=>j.status==='queued'||j.status==='running');
   const injuryHash=evidenceFingerprint((evidence.records||[]).map((r:any)=>({entityKey:r.entityKey,factsHash:r.factsHash,status:r.status,sourceUrl:r.sourceUrl,publicationAt:r.publicationAt})));
   if(!queued.length)return{injuryHash,queued:0,simulationAction:'No owned queued injury jobs; no expensive simulations requested.'};
   return{injuryHash,queued:queued.length,processing:await call('/api/jobs',{action:'run'})};
  });
  if(config.modelAudit)await step('model_evidence_audit',()=>call('/api/audit'));
  const failed=run.steps.filter(s=>s.status==='failed'||s.status==='unavailable').length;
  run.status=failed===0?'completed':failed===run.steps.length?'failed':'partial';run.completedAt=new Date().toISOString();
  await storage.saveRun(run);await storage.setPreference('research_pipeline_state',{lastStartedAt:run.startedAt,lastCompletedAt:run.completedAt,fingerprints});
  return Response.json({run,nextRunAt:new Date(now+config.intervalMinutes*60000).toISOString(),method:'No new model is promoted; unchanged sources do not trigger speculative resimulation.'});
 }finally{active.delete(userId);}
}
