import {cloudContext,requireCloudUser,finishCloud,cloudError} from '@/lib/cloud/context';
import {ApiError,errorResponse,guardMutation,readJsonObject} from '@/lib/auth';
import {workspaceSaveSchema} from '@/lib/workspaces/schema';
import {publicRateLimit} from '@/lib/public-nfl/store';
export const runtime='nodejs';export const dynamic='force-dynamic';
export async function GET(request:Request){let ctx;try{ctx=await cloudContext(request);const owner=requireCloudUser(ctx),q=new URL(request.url).searchParams,id=q.get('id');let query=ctx.client.from(q.has('versions')?'research_workspace_versions':'research_workspaces').select('*').eq('user_id',owner.id);
 if(q.has('versions')&&!id)throw new ApiError('Choose a saved workspace.');
 if(id){if(!/^[a-f\d-]{36}$/i.test(id))throw new ApiError('Invalid workspace identity.');query=query.eq(q.has('versions')?'workspace_id':'id',id);}
 if(q.has('beforeRevision')){const before=Number(q.get('beforeRevision'));if(!q.has('versions')||!Number.isSafeInteger(before)||before<1)throw new ApiError('Choose a valid version page.');query=query.lt('revision',before);}
 if(q.has('versions'))query=query.order('revision',{ascending:false}).limit(100);else query=query.order('updated_at',{ascending:false}).limit(100);
 const{data,error}=await query;if(error)cloudError(error);return finishCloud(ctx,Response.json({records:data??[],limit:100,nextRevision:q.has('versions')&&data?.length===100?data[data.length-1].revision:null}));}catch(e){return finishCloud(ctx,errorResponse(e));}}
export async function POST(request:Request){let ctx;try{guardMutation(request);ctx=await cloudContext(request);requireCloudUser(ctx);await publicRateLimit(request,'workspace-autosave',120,60000);const parsed=workspaceSaveSchema.safeParse(await readJsonObject(request));if(!parsed.success)throw new ApiError('The research draft has invalid fields or exceeds its safe size.');const{data,error}=await ctx.client.rpc('gridiron_save_workspace',{p:parsed.data});if(error){if(['40001','23505'].includes(error.code))throw new ApiError('A newer cloud version exists or this save identity has changed. Reload the cloud version before saving.',409);cloudError(error);}return finishCloud(ctx,Response.json({record:data}));}catch(e){return finishCloud(ctx,errorResponse(e));}}
