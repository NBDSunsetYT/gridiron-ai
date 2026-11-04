/** Hosting policy is independent of UI flags. Vercel must never execute models. */
import {ApiError} from '../auth';
const deferred=new Set<Promise<unknown>>();
export function computeAllowed(){return process.env.VERCEL!=='1'&&process.env.GRIDIRON_COMPUTE_ROLE!=='web'&&(process.env.GRIDIRON_CLOUD_ONLY!=='1'||process.env.GRIDIRON_COMPUTE_ROLE==='worker');}
export function assertComputeAllowed(){if(!computeAllowed())throw new ApiError('This server serves saved predictions. Computation requires the controlled research worker.',409);}
export function deferWorker(work:()=>Promise<unknown>){
 if(!computeAllowed())return;
 const task=Promise.resolve().then(work);deferred.add(task);void task.catch(()=>{}).finally(()=>deferred.delete(task));
}
export async function finishDeferred(){while(deferred.size)await Promise.allSettled([...deferred]);}
