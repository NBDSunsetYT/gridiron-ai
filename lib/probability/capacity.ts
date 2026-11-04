import {cloudClient} from '../cloud/context';
import {ApiError} from '../auth';
/** The existing hard limit is unchanged. Background jobs stop earlier so normal
 * on-demand analysis has reserved capacity. No budget row is reset or refunded. */
export async function probabilityCapacity(){const token=process.env.GRIDIRON_PUBLIC_INGEST_TOKEN;if(!token)throw new ApiError('Research capacity could not be verified.',503);const{data,error}=await cloudClient().rpc('gridiron_probability_capacity',{token});if(error||!Number.isSafeInteger(data?.used)||data?.limit!==500000)throw new ApiError('Research capacity could not be verified.',503);return data as{used:number;limit:number;backgroundLimit:number;resetsAt:string};}
