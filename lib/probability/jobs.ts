import {after} from 'next/server';
import {computeAllowed,deferWorker} from '../compute/policy';
import {enqueueCompute,queueMessage} from '../compute/queue';
import {sharedCache,putCache,publicRateLimit} from '../public-nfl/store';
import {putResearchObject,readResearchObject,isResearchPointer} from '../public-nfl/objects';
import {canonicalJson} from '../cloud/attestation';
import {createHash,randomUUID} from 'node:crypto';
import {ApiError} from '../auth';
import {calculateProbability,unavailable} from './service';
import {evidenceFailure} from './failures';
import type {ProbabilityTarget} from './schema';
const active=new Map<string,Promise<void>>();
const key=(id:string)=>'probability-job:'+id;
function identity(t:ProbabilityTarget):unknown{if(t.type==='prop'){const{cursor,...rest}=t;return rest;}return t.type==='combination'?{...t,legs:t.legs.map(identity)}:t;}
export async function readProbabilityJob(id:string){
 if(!/^[a-f0-9]{64}$/.test(id))throw new ApiError('Choose a valid probability analysis.',400);
 const row=await sharedCache('status',key(id));if(!row||row.data.format!=='probability-job-v1')throw new ApiError('This analysis request was not found. Retry Analysis to create it again.',404);
 const job=row.data;if(job.resultReference&&isResearchPointer(job.resultReference)){const result=await readResearchObject(job.resultReference);if(result.targetKey!==job.targetKey)throw new ApiError('The probability result did not match the saved selection.',502);if(result.kickoff&&Date.parse(result.kickoff)<=Date.now())return{...unavailable(job.target,'This pregame result is historical; a verified live model is unavailable.'),mode:'live_unavailable',state:'source_unavailable',jobId:id,kickoff:result.kickoff};const expiredQuote=result.market?.sourceUpdatedAt&&Date.now()-Date.parse(result.market.sourceUpdatedAt)>300000;return{...result,...expiredQuote?{market:{...result.market,current:false,breakEven:null,priceStatus:'historical_quote_only'}}:{},jobId:id};}
 return{...unavailable(job.target,job.reason??'Research is running on the backend.'),status:job.status,state:job.state,reasonCode:job.reasonCode,jobId:id,retryable:job.retryable??true,retryAt:job.retryAt,retryAfterSeconds:30,updatedAt:row.updated_at};
}
async function run(id:string,target:ProbabilityTarget,count:number,lease:string){
 const update=async(state:string,extra:Record<string,any>={})=>{const current=await sharedCache('status',key(id));if(current?.data.lease!==lease)return;await putCache('status',key(id),{...current.data,status:'pending',state,...extra},id,3600000);};
 try{
  await update('loading_research');
  const result=await calculateProbability(target,count,undefined,{onProgress:async state=>update(state)});
  const resultReference=await putResearchObject(result);
  await update(result.status==='ready'?'ready':result.state??'source_unavailable',{status:result.status,resultReference,targetKey:result.targetKey,reason:result.reason,reasonCode:result.reasonCode,retryable:result.retryable,retryAt:result.retryAt});
 }catch(error){await update('simulation_failed',{status:'unavailable',...evidenceFailure(error)}).catch(()=>{});}
}
export async function requestProbabilityJob(request:Request,target:ProbabilityTarget,count:number){
 const id=createHash('sha256').update(canonicalJson(['probability-job-v2',identity(target),count])).digest('hex'),row=await sharedCache('status',key(id));
 const age=row?Date.now()-Date.parse(row.updated_at):Infinity;
 if(row&&!(process.env.GRIDIRON_COMPUTE_ROLE==='worker'&&row.data.status==='pending')&&(row.data.status==='pending'&&age<300000||row.data.status==='ready'&&age<60000||row.data.status==='unavailable'&&age<15000))return readProbabilityJob(id);
 await publicRateLimit(request,'probability-to-hit',30,3600000);
 const lease=randomUUID(),targetKey=createHash('sha256').update(JSON.stringify(identity(target))).digest('hex');
 await putCache('status',key(id),{format:'probability-job-v1',target,simulations:count,lease,targetKey,status:'pending',state:'resolving_player',reason:'Resolving the exact sport, event, player and market.'},id,3600000);
 if(!computeAllowed()){
  // This read path may evaluate an already-saved histogram. Every engine entry
  // is independently guarded; a miss only queues work, never launches Python.
  const cached=await calculateProbability(target,count);
  if(cached.status==='ready'){
   const resultReference=await putResearchObject(cached);await putCache('status',key(id),{format:'probability-job-v1',target,simulations:count,lease,targetKey:cached.targetKey,status:'ready',state:'ready',resultReference},id,3600000);return readProbabilityJob(id);
  }
  const queued=await enqueueCompute({kind:'probability',request:{target,simulations:count}});return{...await readProbabilityJob(id),computeJobId:queued.id,retryAfterSeconds:30,reason:queueMessage(queued)};
 }
 const execute=async()=>{if(active.has(id))return;const task=run(id,target,count,lease);active.set(id,task);try{await task;}finally{active.delete(id);}};
 if(process.env.GRIDIRON_COMPUTE_ROLE==='worker')deferWorker(execute);else after(execute);
 return readProbabilityJob(id);
}
