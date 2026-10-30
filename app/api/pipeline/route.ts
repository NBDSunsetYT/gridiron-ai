import {requireUser,rateLimit,errorResponse} from '@/lib/auth';
import {getPreferences,setPreference,listResearchRecords,createResearchRecord} from '@/lib/research-store';
import {handlePipeline,PipelineStorage} from '@/lib/pipeline';
export const runtime='nodejs';export const dynamic='force-dynamic';export const maxDuration=900;
async function route(request:Request){try{
 const user=await requireUser(request);if(request.method!=='GET')rateLimit('pipeline:'+user.id,60,3600000);
 const storage:PipelineStorage={preferences:async()=>getPreferences(user.id),setPreference:async(key,value)=>{setPreference(user.id,key,value);},history:async limit=>listResearchRecords(user.id,{kind:'pipeline_run',limit}).map(r=>({...r.data,id:r.id})),saveRun:async run=>{createResearchRecord(user.id,{kind:'pipeline_run',data:run,source:'Owned configured pipeline',observedAt:run.startedAt});}};
 return await handlePipeline(request,user.id,storage);
 }catch(error){return errorResponse(error);}}
export const GET=route;export const POST=route;
