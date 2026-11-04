import {ApiError,errorResponse,guardMutation,readJsonObject} from '../auth';
import {cloudContext,requireCloudUser,finishCloud,CloudAuthUnavailable,type CloudContext,ACCESS_COOKIE,REFRESH_COOKIE} from '../cloud/context';
import {cloudCreateConversation,cloudAppendMessage} from '../cloud/research';
import {publicRateLimit} from '../public-nfl/store';
import {collegeDashboard,collegeGameDetail,analyzeCollegeGame,collegePropScanner,collegeAssistant,collegeSavedResearch,collegeOwnedAnalysis,savePublishedCollegeAnalysis} from './service';

const json=(value:unknown,status=200,publicCache=false)=>Response.json(value,{status,headers:{'Cache-Control':'no-store','X-Content-Type-Options':'nosniff',...(publicCache?{'CDN-Cache-Control':'public, s-maxage=30','Vercel-CDN-Cache-Control':'public, s-maxage=30'}:{})}});
function exact(body:Record<string,unknown>,keys:string[]){if(Object.keys(body).some(key=>!keys.includes(key)))throw new ApiError('This action accepts only the published college-football game and supported options.');}
function hasSession(request:Request){return(request.headers.get('cookie')??'').split(';').some(value=>[ACCESS_COOKIE,REFRESH_COOKIE].some(name=>value.trim().startsWith(name+'=')));}
export async function handleCollegeFootball(request:Request,parts:string[]=[]):Promise<Response>{
 let ctx:CloudContext|undefined;
 try{
  if(!parts.length&&request.method==='GET')return json(await collegeDashboard({date:new URL(request.url).searchParams.get('date')??undefined}),200,true);
  if(parts[0]==='games'&&parts.length>=2){const id=decodeURIComponent(parts[1]);if(parts.length===2&&request.method==='GET')return json(await collegeGameDetail(id));
   if(parts[2]==='analyze'&&parts.length===3&&request.method==='POST'){
    guardMutation(request);const body=await readJsonObject(request);exact(body,['simulations']);const count=body.simulations??10000;if(![10000,50000,100000].includes(count))throw new ApiError('Choose10,000,50,000or100,000 complete college-football games.');
    await publicRateLimit(request,'cfb-analysis',6,3600000);if(hasSession(request))ctx=await cloudContext(request);
    const detail=await analyzeCollegeGame(id,count,ctx);return ctx?finishCloud(ctx,json(detail)):json(detail);
   }
  }
  if(parts[0]==='props'&&(parts.length===1&&request.method==='GET'||parts.length===2&&parts[1]==='analyze'&&request.method==='POST')){
   if(request.method==='POST'){guardMutation(request);const body=await readJsonObject(request);exact(body,[]);await publicRateLimit(request,'cfb-props',12,3600000);}if(hasSession(request))ctx=await cloudContext(request);const scan=await collegePropScanner(ctx);return ctx?finishCloud(ctx,json(scan)):json(scan);
  }
  if(parts[0]==='assistant'&&parts.length===1&&request.method==='POST'){
   guardMutation(request);const body=await readJsonObject(request);exact(body,['gameId','message']);if(typeof body.gameId!=='string'||body.message!==undefined&&(typeof body.message!=='string'||body.message.length>2000))throw new ApiError('Choose a college-football game and a question of at most2,000characters.');await publicRateLimit(request,'cfb-assistant',20,3600000);
   const answer=await collegeAssistant(body.gameId,body.message);if(hasSession(request)){
    try{ctx=await cloudContext(request);if(ctx.user){const conversation=await cloudCreateConversation(ctx,'College football: '+body.gameId);await cloudAppendMessage(ctx,conversation.id,{role:'user',content:body.message??'Explain this college-football game and its uncertainty.',data:{sport:'CFB'}});await cloudAppendMessage(ctx,conversation.id,{role:'assistant',content:answer.summary.text,data:{sport:'CFB',generatedByAI:false,method:answer.summary.method,citations:answer.summary.citations,analysisId:answer.analysisId}});return finishCloud(ctx,json({...answer,historySaved:true,conversationId:conversation.id}));}}catch(error){if(error instanceof CloudAuthUnavailable)ctx=error.context;return finishCloud(ctx,json({...answer,historySaved:false,historyMessage:'This explanation was not saved. Your existing private history is preserved.'}));}
   }return json({...answer,historySaved:false});
  }
  if(['history','saved'].includes(parts[0])&&request.method==='GET'){
   ctx=await cloudContext(request);requireCloudUser(ctx);if(parts.length===1)return finishCloud(ctx,json(await collegeSavedResearch(ctx)));if(parts[0]==='history'&&parts.length===2)return finishCloud(ctx,json(await collegeOwnedAnalysis(ctx,parts[1])));
  }
  if(parts[0]==='save'&&parts.length===1&&request.method==='POST'){
   guardMutation(request);const body=await readJsonObject(request);exact(body,['gameId','analysisId']);if(typeof body.gameId!=='string'||typeof body.analysisId!=='string'||!/^[a-f0-9-]{36}$/i.test(body.analysisId))throw new ApiError('Choose a completed college-football analysis.');ctx=await cloudContext(request);requireCloudUser(ctx);const saved=await savePublishedCollegeAnalysis(ctx,body.gameId,body.analysisId);return finishCloud(ctx,json(saved,saved.duplicate?200:201));
  }
  throw new ApiError('College-football research route not found.',404);
 }catch(error){if(error instanceof CloudAuthUnavailable)ctx=error.context;const response=errorResponse(error);response.headers.set('Cache-Control','no-store');return ctx?finishCloud(ctx,response):response;}
}
