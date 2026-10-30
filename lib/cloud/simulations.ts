import {randomUUID,createHash} from 'node:crypto';
import {ApiError} from '../auth';
import {combineScenarios} from '../jobs';
import {type CloudContext} from './context';
import {records,record,saveRecord,updateRecord,unwrap} from './store';
import {cloudSavePrediction} from './research';
import {attestCloudResult,verifyCloudResult,verifiedCloudJob} from './attestation';
import {simulationPayload} from '../simulation-input';

export function cloudInjuryPayload(input:Record<string,any>,playerId:string,status:string){
 const payload=simulationPayload(input,{replay:true});payload.scenario={playerId,status};
 payload.seed=Number.parseInt(createHash('sha256').update(JSON.stringify({seed:input.seed??1,playerId,status,model:input.model?.sha256??null})).digest('hex').slice(0,12),16);
 return payload;
}

export async function simulationService(action:'fit'|'simulate',payload:Record<string,any>){
 const endpoint=process.env.SIMULATION_SERVICE_URL,token=process.env.SIMULATION_SERVICE_TOKEN;
 if(!endpoint||!token||token.length<32)throw new ApiError('The private quantitative service is not configured. No simulations or model evidence were invented.',503);
 const base=new URL(endpoint.endsWith('/')?endpoint:endpoint+'/');if(!['http:','https:'].includes(base.protocol))throw new ApiError('Invalid quantitative service configuration.',503);
 const statisticalPayload=simulationPayload(payload);
 let response:Response;try{response=await fetch(new URL(action,base),{method:'POST',headers:{'Content-Type':'application/json',Authorization:`Bearer ${token}`},body:JSON.stringify(statisticalPayload),signal:AbortSignal.timeout(240000),cache:'no-store'});}catch{throw new ApiError('The quantitative service was unavailable or timed out. Previous saved results remain intact.',502);}
 let result:any;try{result=await response.json();}catch{throw new ApiError('The quantitative service returned invalid JSON.',502);}
 if(!response.ok)throw new ApiError(typeof result.detail==='string'?result.detail.slice(0,1500):'The quantitative service rejected the supplied evidence.',response.status>=400&&response.status<500?response.status:502);
 return result;
}
export async function cloudRunSimulation(ctx:CloudContext,input:any){
 if(!input||!['fit','simulate'].includes(input.action))throw new ApiError('Choose fit or simulate.');
 // A signed fitted artifact can exceed browser/proxy request limits. Retrieve
 // the caller-owned attested artifact server-side rather than resending it.
 if(input.action==='simulate'&&input.modelJobId){
  if(typeof input.modelJobId!=='string'||!/^[a-f0-9-]{36}$/i.test(input.modelJobId))throw new ApiError('A valid owned fitted-model job ID is required.');
  const fitted=(await record(ctx,input.modelJobId,'simulation_jobs')).data;
  if(fitted.kind!=='fit'||fitted.status!=='completed'||!fitted.result?.model)throw new ApiError('A completed fitted-model job is required.');
  verifyCloudResult(ctx,input.modelJobId,fitted);
  input={...input,model:fitted.result.model};delete input.modelJobId;
 }
 // Refuse to record a pretend pending run when the service is absent.
 if(!process.env.SIMULATION_SERVICE_URL||!process.env.SIMULATION_SERVICE_TOKEN)throw new ApiError('SIMULATION_SERVICE_URL and SIMULATION_SERVICE_TOKEN are not configured.',503);
 const {action,...payload}=input;simulationPayload(payload);
 const id=randomUUID(),now=new Date().toISOString(),job={id,kind:action,status:'running',data:{inputHash:createHash('sha256').update(JSON.stringify(input)).digest('hex'),home:input.home??null,away:input.away??null,eventStart:input.eventStart??null,simulations:input.simulations??null,modelVersion:input.model?.version??null,source:input.source??input.model?.source??null,scenario:input.scenario??null,contracts:input.contracts??null,injuryEntityKeys:input.injuryEntityKeys??[]},result:null as any,error:null as string|null,createdAt:now,updatedAt:now};
 await saveRecord(ctx,'simulation_jobs',job,{id});
 try{
  await saveRecord(ctx,'simulation_inputs',{id:randomUUID(),jobId:id,input},{entityKey:id});
  const result=await simulationService(action,payload);job.status='completed';job.result=result;job.updatedAt=new Date().toISOString();await updateRecord(ctx,id,{...job,resultProof:attestCloudResult(ctx,id,result)});
  return{id,status:'completed',...result};
 }catch(error){job.status='failed';job.error=error instanceof ApiError?error.message:'Simulation failed.';job.updatedAt=new Date().toISOString();await updateRecord(ctx,id,job);throw error;}
}
export async function cloudSimulationHistory(ctx:CloudContext,id?:string|null){
 const configured=Boolean(process.env.SIMULATION_SERVICE_URL&&process.env.SIMULATION_SERVICE_TOKEN);
 if(id)return{job:verifiedCloudJob(ctx,(await record(ctx,id,'simulation_jobs')).data),service:{configured}};
 return{jobs:unwrap(await records(ctx,'simulation_jobs',{limit:60})).map(j=>verifiedCloudJob(ctx,j)).map(j=>({...j,result:j.result?{summary:j.result.summary,modelVersion:j.result.modelVersion,provenance:j.result.provenance,simulations:j.result.simulations,home:j.result.home,away:j.result.away}:null})),service:{configured,message:configured?'Service configured; requests verify actual availability.':'Private service not configured.'}};
}
export async function cloudJobHistory(ctx:CloudContext){return{jobs:unwrap(await records(ctx,'simulation_jobs',{limit:100,dataKind:'injury_resimulation'})),worker:{onInjurySave:true,recovery:'Owned queued jobs can be resumed after sign-in. Background server-wide cron needs an explicitly configured privileged worker; no user JWT is invented.'}};}
export async function cloudProcessJobs(ctx:CloudContext,limit=1){
 const bounded=Math.max(1,Math.min(3,Math.trunc(limit)||1)),cutoff=new Date(Date.now()-20*60000).toISOString();
 const [queued,interrupted]=await Promise.all([records(ctx,'simulation_jobs',{limit:bounded,dataKind:'injury_resimulation',dataStatus:'queued',oldestFirst:true}),records(ctx,'simulation_jobs',{limit:bounded,dataKind:'injury_resimulation',dataStatus:'running',beforeUpdatedAt:cutoff,oldestFirst:true})]);
 const jobs=unwrap([...queued,...interrupted]).sort((a,b)=>Date.parse(a.createdAt)-Date.parse(b.createdAt));const results:any[]=[];
 for(const job of jobs.slice(0,Math.min(3,limit))){
  const previousStatus=job.status,claimed={...job,status:'running',updatedAt:new Date().toISOString()};
  const claim=await ctx.client.from('gridiron_records').update({data:claimed,updated_at:claimed.updatedAt}).eq('id',job.id).eq('kind','simulation_jobs').eq('data->>status',previousStatus).select('id');
  if(claim.error||!claim.data?.length)continue;
  try{
   const sourceJobId=job.data?.sourceJobId,predictionId=job.data?.predictionId,injuryRecordId=job.data?.injuryRecordId;
   const sourceJob=(await record(ctx,sourceJobId,'simulation_jobs')).data;verifyCloudResult(ctx,sourceJobId,sourceJob);
   const inputs=(await records(ctx,'simulation_inputs',{entityKey:sourceJobId,limit:1}))[0]?.data?.input;
   if(!inputs)throw new ApiError('Complete original signed simulation inputs are unavailable.');
   const injury=(await record(ctx,injuryRecordId,'injury_history')).data,prediction=(await record(ctx,predictionId,'prediction_snapshots')).data;
   const previousPlayer=inputs.scenario?.playerId??inputs.injuryMixture?.playerId;if(previousPlayer&&previousPlayer!==injury.entityKey)throw new ApiError('Joint multiple-player injury evidence is not modeled; automatic replay is blocked.');
   if(Date.parse(inputs.eventStart)<=Date.now())throw new ApiError('The event has started; no new pre-event projection can be made.');
   if(Date.now()-Date.parse(injury.checkedAt)>86400000||Date.now()-Date.parse(injury.publicationAt)>259200000)throw new ApiError('Injury evidence is stale.');
   const cohort=injury.cohorts,total=cohort?cohort.active+cohort.limited+cohort.out:0;
   const scenarios=['out','injured_reserve','suspended'].includes(injury.status)?[{status:'inactive',weight:1}]:total>=20?[{status:'active',weight:cohort.active/total},{status:'limited',weight:cohort.limited/total},{status:'inactive',weight:cohort.out/total}].filter(s=>s.weight>0):null;
   if(!scenarios)throw new ApiError('Uncertain availability has insufficient documented cohort outcomes.');
   const values:any[]=[];for(const scenario of scenarios){values.push(await simulationService('simulate',cloudInjuryPayload(inputs,injury.entityKey,scenario.status)));}
   const result=combineScenarios(values,scenarios.map(s=>s.weight)),completed={...claimed,status:'completed',result,resultProof:attestCloudResult(ctx,job.id,result),error:null,updatedAt:new Date().toISOString()};
   await updateRecord(ctx,job.id,completed);await saveRecord(ctx,'simulation_inputs',{jobId:job.id,input:{...inputs,injuryMixture:{playerId:injury.entityKey,scenarios}}},{entityKey:job.id});
   let next:any=null;try{const latestQuote=unwrap(await records(ctx,'contract_quotes',{entityKey:prediction.contractId,limit:1}))[0];next=await cloudSavePrediction(ctx,{...prediction,quoteId:latestQuote?.id??prediction.quoteId,asOf:new Date().toISOString(),supersedesPredictionId:prediction.id,injuryEntityKeys:Array.from(new Set([...(prediction.injuryEntityKeys??[]),injury.entityKey])),evidence:{source:'Evidence-backed injury replay of '+sourceJobId,method:'Complete-game historical availability scenarios',sampleSize:result.simulations,simulationId:job.id}});}catch(error){await saveRecord(ctx,'notification_history',{type:'resimulation_requires_review',jobId:job.id,reason:error instanceof Error?error.message:'New valuation requires review.',createdAt:new Date().toISOString()});}
   await saveRecord(ctx,'notification_history',{type:'resimulation_completed',jobId:job.id,predictionId:next?.id??null,previousPredictionId:predictionId,createdAt:new Date().toISOString(),delivery:'in_app_only'});results.push({id:job.id,status:'completed'});
  }catch(error){const message=error instanceof Error?error.message:'Injury replay failed.';await updateRecord(ctx,job.id,{...claimed,status:'blocked',error:message,updatedAt:new Date().toISOString()});await saveRecord(ctx,'notification_history',{type:'resimulation_blocked',jobId:job.id,reason:message,createdAt:new Date().toISOString()});results.push({id:job.id,status:'blocked',reason:message});}
 }
 return{processed:results.length,jobs:results};
}
