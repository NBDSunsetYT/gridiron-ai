import {freeProps} from '@/lib/free-props-service';
import {errorResponse,guardMutation,readJsonObject,ApiError} from '@/lib/auth';
import {cloudContext,requireCloudUser,finishCloud,ACCESS_COOKIE,REFRESH_COOKIE,type CloudContext} from '@/lib/cloud/context';
import {saveRecord,records} from '@/lib/cloud/store';
import {publicRateLimit} from '@/lib/public-nfl/store';
import {measure} from '@/lib/performance/metrics';
export const runtime='nodejs';export const dynamic='force-dynamic';export const maxDuration=300;
async function handle(request:Request,analyze:boolean){let ctx:CloudContext|undefined;try{
 const q=new URL(request.url).searchParams;if(q.get('history')==='1'){const selected=q.get('sport')??'NFL';if(!['NFL','CFB'].includes(selected))throw new ApiError('Choose NFL or CFB.');ctx=await cloudContext(request);requireCloudUser(ctx);const rows=await records(ctx,'research_records/propline_snapshot',{limit:5,entityKey:selected});return finishCloud(ctx,Response.json({saved:rows.map(r=>r.data)},{headers:{'Cache-Control':'no-store'}}));}const sport=q.get('sport')??'NFL',cursor=Number(q.get('cursor')??0);if(!['NFL','CFB'].includes(sport)||!Number.isSafeInteger(cursor)||cursor<0||cursor>50000)throw new ApiError('Choose NFL or CFB and a valid page.');
 if(analyze){guardMutation(request);const body=await readJsonObject(request);if(Object.keys(body).length)throw new ApiError('No client statistics, credentials or model outputs accepted.');await publicRateLimit(request,'propline-analysis',6,3600000);}
 if(analyze&&[ACCESS_COOKIE,REFRESH_COOKIE].some(key=>(request.headers.get('cookie')??'').split(';').some(part=>part.trim().startsWith(key+'=')))){ctx=await cloudContext(request);requireCloudUser(ctx);}
 const value=await freeProps(sport as 'NFL'|'CFB',cursor,analyze,ctx);
 if(ctx){const saved=await saveRecord(ctx,'research_records/propline_snapshot',{sport,provider:'PropLine',observedAt:new Date().toISOString(),items:value.items.slice(0,100),totalResults:value.totalResults,analysisScope:'First100rows of the requested bounded page; full feed count is separate.'},{source:'Verified PropLine Render gateway',entityKey:sport});(value as any).privateSnapshot={saved:true,id:saved.id};}
 const response=Response.json(value,{headers:{'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'}});return ctx?finishCloud(ctx,response):response;
 }catch(error){return finishCloud(ctx,errorResponse(error));}}
export const GET=(request:Request)=>measure('props_get',()=>handle(request,false));
export const POST=(request:Request)=>measure('props_post',()=>handle(request,true));
