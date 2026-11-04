import {cloudContext,finishCloud,type CloudContext,ACCESS_COOKIE,REFRESH_COOKIE} from '@/lib/cloud/context';
import {ApiError,errorResponse,guardMutation,readJsonObject} from '@/lib/auth';
import {probabilityRequest} from '@/lib/probability/schema';
import {saveProbability,probabilityHistory,applyProbabilityCalibration} from '@/lib/probability/service';
import {readProbabilityJob,requestProbabilityJob} from '@/lib/probability/jobs';
export const runtime='nodejs';export const dynamic='force-dynamic';export const maxDuration=300;
async function identity(request:Request){return[ACCESS_COOKIE,REFRESH_COOKIE].some(k=>(request.headers.get('cookie')??'').includes(k+'='))?cloudContext(request):undefined;}
async function resultResponse(value:any,ctx?:CloudContext){
 if(value.status==='ready')await applyProbabilityCalibration(value,value.target,ctx);
 try{value.persistence=ctx?.user&&value.status==='ready'?await saveProbability(ctx,value):{saved:false,reason:value.status==='ready'?'Guest analysis; sign in for permanent personal history.':'Pending or unsupported estimates are not saved as predictions.'};if(ctx?.user&&value.targetKey)value.history=await probabilityHistory(ctx,value.targetKey);}catch{value.persistence={saved:false,reason:'Cloud history could not be confirmed. Retry to save; existing records are preserved.'};}
 return finishCloud(ctx,Response.json(value,{status:value.status==='pending'?202:200,headers:{'Cache-Control':'no-store',...value.status==='pending'?{'Retry-After':'3'}:{}}}));
}
export async function GET(request:Request){let ctx:CloudContext|undefined;try{ctx=await identity(request);const query=new URL(request.url).searchParams;if(query.has('jobId'))return await resultResponse(await readProbabilityJob(query.get('jobId')!),ctx);ctx??=await cloudContext(request);const key=query.get('targetKey')??'';if(!/^[a-f0-9]{64}$/.test(key))throw new ApiError('Choose a valid probability history.');return finishCloud(ctx,Response.json({history:await probabilityHistory(ctx,key)},{headers:{'Cache-Control':'no-store'}}));}catch(e){return finishCloud(ctx,errorResponse(e));}}
export async function POST(request:Request){let ctx:CloudContext|undefined;try{guardMutation(request);const p=probabilityRequest.safeParse(await readJsonObject(request));if(!p.success)throw new ApiError('Choose a supported market and 10,000, 50,000 or 100,000 complete games.');ctx=await identity(request);return await resultResponse(await requestProbabilityJob(request,p.data.target,p.data.simulations),ctx);}catch(e){return finishCloud(ctx,errorResponse(e));}}
