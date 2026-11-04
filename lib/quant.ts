import {assertComputeAllowed} from './compute/policy';
import {randomUUID,createHash} from 'node:crypto';
import {ApiError,requestOrigin} from './auth';
export type QuantStorage={save:(job:Record<string,any>)=>Promise<void>;list:()=>Promise<Record<string,any>[]>;get:(id:string)=>Promise<Record<string,any>|null>};
/** Shared statistical-service boundary; callers authenticate and supply owner-scoped persistence. */
export async function handleQuant(request:Request,_userId:string,storage:QuantStorage){
 const configured=Boolean(process.env.SIMULATION_SERVICE_URL&&process.env.SIMULATION_SERVICE_TOKEN);
 if(request.method==='GET'){
  const id=new URL(request.url).searchParams.get('id');if(id){const job=await storage.get(id);if(!job)throw new ApiError('Owned quantitative run not found.',404);return Response.json({job,configured});}
  return Response.json({jobs:await storage.list(),configured});
 }
 assertComputeAllowed();
 if(request.headers.get('origin')&&request.headers.get('origin')!==requestOrigin(request))throw new ApiError('Cross-origin requests are not allowed.',403);
 if(!/^application\/json(?:;|$)/i.test(request.headers.get('content-type')||''))throw new ApiError('Use application/json.',415);
 if(!configured)throw new ApiError('Configure the private Python statistical service. No substitute model or output was generated.',503);
 const reader=request.body?.getReader();if(!reader)throw new ApiError('A statistical request is required.');let bytes=0;const chunks:Uint8Array[]=[];
 for(;;){const {done,value}=await reader.read();if(done)break;bytes+=value.byteLength;if(bytes>25_000_000){await reader.cancel();throw new ApiError('Quantitative input exceeds 25 MB.',413);}chunks.push(value);}
 const text=Buffer.concat(chunks).toString('utf8'),input=JSON.parse(text),{action,...payload}=input;
 const paths:Record<string,string>={benchmark:'models/benchmark',predict:'models/predict',trace:'trace'};
 if(!paths[action])throw new ApiError('Choose benchmark, predict or trace.');
 if(action==='benchmark'&&(typeof input.csv!=='string'||typeof input.source!=='string'||input.source.length<3))throw new ApiError('Actual game history and source provenance are required.');
 const id=randomUUID(),now=new Date().toISOString();const job:Record<string,any>={id,kind:action,status:'running',createdAt:now,updatedAt:now,data:{inputHash:createHash('sha256').update(text).digest('hex'),source:input.source??null,asOf:input.asOf??null,home:input.home??null,away:input.away??null,eventStart:input.eventStart??null}};
 await storage.save(job);
 try{
  const base=process.env.SIMULATION_SERVICE_URL!,response=await fetch(new URL(paths[action],base.endsWith('/')?base:base+'/'),{method:'POST',headers:{'content-type':'application/json',Authorization:`Bearer ${process.env.SIMULATION_SERVICE_TOKEN}`},body:JSON.stringify(payload),signal:AbortSignal.timeout(240000),cache:'no-store'});
  const result=await response.json();if(!response.ok)throw new ApiError(typeof result.detail==='string'?result.detail:'The statistical service rejected the evidence.',response.status>=400&&response.status<500?response.status:502);
  job.status='completed';job.result=result;job.updatedAt=new Date().toISOString();await storage.save(job);
  return Response.json({id,...result});
 }catch(error){job.status='failed';job.error=error instanceof ApiError?error.message:'The statistical service could not complete this run.';job.updatedAt=new Date().toISOString();await storage.save(job);if(error instanceof ApiError)throw error;throw new ApiError(job.error,502);}
}
