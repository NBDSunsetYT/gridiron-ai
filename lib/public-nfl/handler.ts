import {computeAllowed} from '../compute/policy';
import {enqueueCompute} from '../compute/queue';
import {timingSafeEqual,createHash} from 'node:crypto';
import {after} from 'next/server';
import {ApiError,errorResponse,guardMutation,readJsonObject} from '../auth';
import {cloudContext,requireCloudUser,finishCloud,CloudAuthUnavailable,type CloudContext,ACCESS_COOKIE,REFRESH_COOKIE} from '../cloud/context';
import {cloudCreateConversation,cloudAppendMessage} from '../cloud/research';
import {saveRecord,record} from '../cloud/store';
import {warehouseId} from '../warehouse';
import {publicDashboard,publicGameDetail,analyzePublicGame,publicAssistant,refreshPublicResearch} from './service';
import {publicRateLimit,sharedJob,putCache} from './store';
import {signedRefreshAuthorized} from './refresh-auth';

function json(value:unknown,status=200,publicCache=false){return Response.json(value,{status,headers:{'Cache-Control':publicCache?'public, max-age=0, s-maxage=20, stale-while-revalidate=40':'no-store','X-Content-Type-Options':'nosniff',...(publicCache?{'CDN-Cache-Control':'public, s-maxage=20, stale-while-revalidate=40','Vercel-CDN-Cache-Control':'public, s-maxage=20, stale-while-revalidate=40'}:{})}});}
function exactFields(value:Record<string,any>,allowed:string[]){if(Object.keys(value).some(k=>!allowed.includes(k)))throw new ApiError('This action accepts only the game and supported research options.');}
function configuredBearer(request:Request){
 const supplied=request.headers.get('authorization'),secrets=[process.env.GRIDIRON_PUBLIC_INGEST_TOKEN,process.env.CRON_SECRET].filter((v):v is string=>Boolean(v&&v.length>=32));
 return secrets.some(secret=>{const expected=Buffer.from('Bearer '+secret),actual=Buffer.from(supplied||'');return expected.length===actual.length&&timingSafeEqual(expected,actual);});
}
export async function handlePublicNfl(request:Request,parts:string[]=[]):Promise<Response>{
 let privateContext:CloudContext|undefined;
 try{
  if(parts.length===0&&request.method==='GET')return json(await publicDashboard(),200,true);
  if(parts[0]==='refresh'&&parts.length===1){
   if(!['GET','POST'].includes(request.method))throw new ApiError('Method not supported.',405);
   if(!configuredBearer(request)&&!await signedRefreshAuthorized(request))throw new ApiError('Research refresh authorization required.',401);
   if(!computeAllowed()){const job=await enqueueCompute({kind:'maintenance'});return json({status:'scheduled',jobId:job.id,message:'A shared refresh is queued. Web requests never execute background models or audits.'},202);}
   const queuedAt=new Date().toISOString();
   after(async()=>{
    let status:Record<string,any>;
    try{
     status={...await refreshPublicResearch(),status:'completed',queuedAt,completedAt:new Date().toISOString()};
     // The existing authenticated database schedule also continues player-prop
     // ingestion and prospective model auditing. Personal wagers are never settled.
     const props=await import('../player-props/service');
     status.playerProps=await props.refreshPropResearch();status.completedAt=new Date().toISOString();
     after(async()=>{
      // These independent, bounded historical audits never run on dashboard
      // reads and never settle or modify a personal financial record.
      await Promise.allSettled([
       import('../player-props/model-lab').then(lab=>lab.refreshPropModelLab()),
       import('../player-props/game-performance').then(lab=>lab.refreshGameMarketAudit())
       ,import('../learning/service').then(lab=>lab.refreshFootballLearning())
      ]);
     });
    }
    catch{status={status:'failed',queuedAt,completedAt:new Date().toISOString(),message:'Automatic refresh is temporarily unavailable. Previously saved research remains available.'};}
    status.additionalFootball=await(await import('../football-refresh')).refreshAdditionalFootballResearch();
    if(process.env.GRIDIRON_MONGODB_RESEARCH==='1')status.storageSynchronization=await(await import('../storage/outbox')).deliverResearchQueue(5).catch(()=>({status:'unavailable',message:'Durable queued research remains staged.'}));
    await putCache('status','background',status,createHash('sha256').update(JSON.stringify(status)).digest('hex'),86400000).catch(()=>{});
   });
   return json({status:'scheduled',queuedAt,message:'Published NFL information will refresh in the background.'},202);
  }
  if(parts[0]==='games'&&parts.length>=2){const gameId=decodeURIComponent(parts[1]);
   if(parts.length===2&&request.method==='GET'){const detail=await publicGameDetail(gameId);return json(detail);}
   if(parts.length===3&&parts[2]==='analyze'&&request.method==='POST'){
    guardMutation(request);const input=await readJsonObject(request);exactFields(input,['simulations']);await publicRateLimit(request,'nfl-analysis',12,3600000);
    const count=input.simulations===undefined?10000:input.simulations;if(!Number.isInteger(count))throw new ApiError('Choose a supported number of complete games.');
    const detail=await analyzePublicGame(gameId,count);return json(detail,['queued','running'].includes(detail.status)?202:200);
   }
  }
  if(parts[0]==='assistant'&&parts.length===1&&request.method==='POST'){
   guardMutation(request);const input=await readJsonObject(request);exactFields(input,['gameId','message']);if(typeof input.gameId!=='string'||input.message!==undefined&&(typeof input.message!=='string'||input.message.length>2000))throw new ApiError('Choose an NFL game and a question of at most 2,000 characters.');await publicRateLimit(request,'nfl-public-assistant',20,3600000);
   const answer=await publicAssistant(input.gameId,input.message);
   // Guest research never creates a user identity. A signed-in app account can
   // retain its own conversation through a separate user-scoped write path.
   if((request.headers.get('cookie')||'').split(';').some(c=>c.trim().startsWith(ACCESS_COOKIE+'=')||c.trim().startsWith(REFRESH_COOKIE+'='))){
    try{privateContext=await cloudContext(request);if(privateContext.user){const conversation=await cloudCreateConversation(privateContext,`Game research: ${input.gameId}`);await cloudAppendMessage(privateContext,conversation.id,{role:'user',content:input.message||'Explain this game and its uncertainty.'});await cloudAppendMessage(privateContext,conversation.id,{role:'assistant',content:answer.summary.text,data:{generatedByAI:answer.summary.generatedByAI,method:answer.summary.method,citations:answer.summary.citations,publicAnalysisId:answer.analysisId}});return finishCloud(privateContext,json({...answer,conversationId:conversation.id,historySaved:true}));}}catch(error){if(error instanceof CloudAuthUnavailable)privateContext=error.context;return finishCloud(privateContext,json({...answer,historySaved:false,historyMessage:'This explanation could not be saved to your private history. Your existing conversations are unchanged.'}));}
   }
   return privateContext?finishCloud(privateContext,json({...answer,historySaved:false})):json(answer);
  }
  if(parts[0]==='save'&&parts.length===1&&request.method==='POST'){
   guardMutation(request);const input=await readJsonObject(request);exactFields(input,['gameId','analysisId']);if(typeof input.gameId!=='string'||typeof input.analysisId!=='string'||!/^[a-f0-9-]{36}$/i.test(input.analysisId))throw new ApiError('A completed game analysis is required.');
   const ctx=await cloudContext(request);privateContext=ctx;if(!ctx.user)throw new ApiError('Sign in to GRIDIRON AI to save this analysis to your private account.',401);const user=requireCloudUser(ctx),job=await sharedJob(input.analysisId);
   if(!job||job.game_id!==input.gameId||job.status!=='completed'||!job.result)throw new ApiError('A completed published game analysis is required.',404);
   const id=warehouseId(user.id,'public_simulation',job.id),old=await record(ctx,id,'research_records/saved_simulation').catch(error=>{if(error instanceof ApiError&&error.status===404)return null;throw error;});
   const {savedNflReference}=await import('../storage/saved-nfl');
   if(!old)await saveRecord(ctx,'research_records/saved_simulation',{id,publicAnalysisId:job.id,gameId:job.game_id,modelVersion:job.result.result?.modelVersion,summary:job.result.summary,resultReference:savedNflReference(job),source:'GRIDIRON published automatic NFL research',savedAt:new Date().toISOString()},{id,entityKey:job.game_id});
   return finishCloud(ctx,json({saved:true,id,analysisId:job.id,private:true},old?200:201));
  }
  throw new ApiError('NFL research route not found.',404);
 }catch(error){if(error instanceof CloudAuthUnavailable)privateContext=error.context;const response=errorResponse(error);response.headers.set('Cache-Control','no-store');return privateContext?finishCloud(privateContext,response):response;}
}
