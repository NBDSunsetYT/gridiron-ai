/** Capability-only public research tasks. Never store sessions or private records. */
import {createHash} from 'node:crypto';
import {z} from 'zod';
import {cloudClient} from '../cloud/context';
import {ApiError} from '../auth';
import {canonicalJson} from '../cloud/attestation';
import {performanceEvent,measure} from '../performance/metrics';
import {probabilityRequest} from '../probability/schema';
export const TASK_VERSION='bounded-compute-1';
const count=z.union([z.literal(10000),z.literal(50000),z.literal(100000)]);
export const taskSchema=z.discriminatedUnion('kind',[
 z.object({kind:z.literal('game'),sport:z.enum(['NFL','CFB','NBA']),gameId:z.string().min(1).max(100),simulations:count.default(10000),inputVersion:z.string().regex(/^[a-f0-9]{64}$/).optional()}).strict(),
 z.object({kind:z.literal('probability'),request:probabilityRequest}).strict(),
 z.object({kind:z.literal('prop_scan'),runId:z.string().uuid()}).strict(),
 z.object({kind:z.literal('maintenance')}).strict()
]).superRefine((t,c)=>{if(t.kind==='game'&&!({NFL:/^\d{4}_\d{2,3}_[A-Z0-9]{2,3}_[A-Z0-9]{2,3}$/,CFB:/^cfb:espn:\d{6,12}$/,NBA:/^nba:espn:\d{1,12}$/}[t.sport]).test(t.gameId))c.addIssue({code:'custom',message:'Sport and event identity must match.'});});
export type ComputeTask=z.infer<typeof taskSchema>;
export async function computeOperation(payload:Record<string,unknown>){
 const token=process.env.GRIDIRON_PUBLIC_INGEST_TOKEN;if(!token||token.length<40)throw new ApiError('The durable computation queue is not configured. Saved research is preserved.',503);
 performanceEvent('compute_queue','database');const {data,error}=await cloudClient().rpc('gridiron_compute_jobs',{token,payload});
 if(error)throw new ApiError('The durable computation queue is unavailable. No simulation was started on the web server.',503);return data;
}
const active=new Map<string,Promise<any>>(),recent=new Map<string,{until:number;value:any}>();
export function computeTaskId(input:ComputeTask){return createHash('sha256').update(canonicalJson([TASK_VERSION,input])).digest('hex');}
export async function enqueueCompute(input:unknown){
 const task=taskSchema.parse(input),id=computeTaskId(task),cached=recent.get(id);if(cached&&cached.until>Date.now())return cached.value;
 if(active.has(id))return active.get(id);
 const pending=measure('compute_enqueue',async()=>{const value=await computeOperation({action:'enqueue',id,task,version:TASK_VERSION});if(recent.size>=128)recent.delete(recent.keys().next().value!);recent.set(id,{until:Date.now()+30000,value});return value;});
 active.set(id,pending);try{return await pending;}finally{active.delete(id);}
}
export function queueMessage(job:any){return job.status==='delayed'?'Research is waiting for the controlled worker retry window. Saved predictions remain available.':'Research is queued for the controlled worker. Refreshing this page does not start a simulation.';}
