/** Actual deployed guest acceptance. No accounts, passwords, CSV uploads or
 * financial writes. A standard game analysis may be queued through the same
 * public action offered by the app. Never substitute synthetic production data. */
import {mkdirSync,writeFileSync} from 'node:fs';
import {dirname} from 'node:path';
import assert from 'node:assert/strict';
import {EnvHttpProxyAgent,setGlobalDispatcher} from 'undici';
import {assertNoPrivateResearchFields,assertPublicGameDetail} from './helpers/public-acceptance.mjs';

if(process.env.HTTPS_PROXY||process.env.HTTP_PROXY||process.env.https_proxy||process.env.http_proxy)setGlobalDispatcher(new EnvHttpProxyAgent());
const base=new URL(process.env.BASE_URL||'https://gridiron-ai-gray.vercel.app');
assert.ok(base.protocol==='https:'||(base.protocol==='http:'&&['localhost','127.0.0.1'].includes(base.hostname)),'Deployed guest acceptance requires HTTPS; local full-stack checks may use loopback.');
const report={status:'running',startedAt:new Date().toISOString(),baseUrl:base.origin,environment:base.protocol==='https:'?'production_https':'local_fullstack',guest:true,accountsCreated:false,financialWrites:false,csvUploads:false,physicalIphoneInstallationTested:false,checks:[]};
const target=process.env.QA_REPORT_PATH||'docs/reports/v5-production-public-workflow.json';
const write=()=>{mkdirSync(dirname(target),{recursive:true});writeFileSync(target,JSON.stringify(report,null,2)+'\n');};
const mark=name=>{report.checks.push({name,status:'passed'});console.log(JSON.stringify({check:name,status:'passed'}));};
const pause=ms=>new Promise(resolve=>setTimeout(resolve,ms));
async function call(path,body){
 const response=await fetch(new URL(path,base),{method:body===undefined?'GET':'POST',headers:{'Content-Type':'application/json',Origin:base.origin},body:body===undefined?undefined:JSON.stringify(body),signal:AbortSignal.timeout(90000),redirect:'manual',cache:'no-store'});
 const text=await response.text();let data;try{data=JSON.parse(text);}catch{data=null;}
 assert.equal(response.headers.get('location'),null,'Guest research must not redirect into an external developer dashboard.');
 return{status:response.status,data,cacheControl:response.headers.get('cache-control')};
}
try{
 const auth=await call('/api/auth');assert.equal(auth.status,200);assert.equal(auth.data.user,null);mark('A fresh visitor has no app identity and is not redirected to a developer dashboard');
 let dashboard;
 const scheduleDeadline=Date.now()+120000;
 while(Date.now()<scheduleDeadline){const response=await call('/api/nfl');assert.ok([200,202].includes(response.status),response.data?.error);dashboard=response.data;assertNoPrivateResearchFields(dashboard);if(dashboard.games?.length)break;await pause(3000);}
 assert.equal(dashboard?.guestAccess,true);assert.ok(dashboard.games?.length>0,'An actual NFL schedule must load automatically for guests.');
 const candidates=dashboard.games.filter(game=>game.status==='scheduled'&&Date.parse(game.startTime)>Date.now()).sort((a,b)=>Date.parse(a.startTime)-Date.parse(b.startTime));
 const game=process.env.QA_GAME_ID?dashboard.games.find(game=>game.id===process.env.QA_GAME_ID):candidates[0];
 assert.ok(game,'An upcoming actual NFL game is required; no historical or synthetic substitute is accepted.');
 assert.ok(!/SYNTHETIC|DEMO/i.test(JSON.stringify(game)),'Production schedule evidence must not be a synthetic development fixture.');
 report.game={id:game.id,home:game.home.abbreviation,away:game.away.abbreviation,startTime:game.startTime};mark('Upcoming NFL games load from published sources without sign-in or a CSV upload');
 let response=await call('/api/nfl/games/'+encodeURIComponent(game.id));assert.equal(response.status,200,response.data?.error);let detail=response.data;assertPublicGameDetail(detail);
 if(detail.analysis?.status!=='completed'||detail.analysis?.stale){response=await call('/api/nfl/games/'+encodeURIComponent(game.id)+'/analyze',{});assert.ok([200,202].includes(response.status),response.data?.error);detail=response.data;}
 const deadline=Date.now()+(Number(process.env.QA_SIMULATION_DEADLINE_MS)||900000);let previous;
 while(Date.now()<deadline){
  response=await call('/api/nfl/games/'+encodeURIComponent(game.id));assert.ok([200,202].includes(response.status),response.data?.error);detail=response.data;assertPublicGameDetail(detail);
  const state=detail.analysis?.status??detail.status;
  if(state!==previous){console.log(JSON.stringify({gameId:game.id,analysisStatus:state}));previous=state;}
  if(state==='completed'&&!detail.analysis.stale)break;
  if(state==='failed')throw Error(detail.analysis?.error||detail.message||'The actual automatic analysis failed.');
  await pause(4000);
 }
 assert.equal(detail.analysis?.status,'completed','No complete result was retrieved within the bounded acceptance deadline.');
 report.simulation=assertPublicGameDetail(detail,{completed:true});assert.equal(report.simulation.completeGames,10000);report.analysisId=detail.analysis.id;
 report.coverage={injuries:detail.injuries.status,weather:detail.weather.status,markets:detail.markets.status};report.sourceCount=detail.sources.length;
 mark('Automatic trusted-data preparation and 10,000 coherent complete games produce player and game distributions');
 const repeated=await call('/api/nfl/games/'+encodeURIComponent(game.id)+'/analyze',{});assert.equal(repeated.status,200,repeated.data?.error);assert.equal(repeated.data.analysis?.id,detail.analysis.id,'A fresh cached result must be reused instead of creating a duplicate simulation.');mark('A repeated Analyze Game action reuses the same fresh persisted result');
 const assistant=await call('/api/nfl/assistant',{gameId:game.id,message:'Explain this game analysis, the simulation evidence, injury uncertainty, and unavailable prices. Cite your sources.'});
 assert.equal(assistant.status,200,assistant.data?.error);assertNoPrivateResearchFields(assistant.data);const summary=assistant.data.summary;assert.ok(summary?.text?.length>0&&summary.citations?.length>0);assert.ok(typeof summary.generatedByAI==='boolean');assert.equal(summary.method,summary.generatedByAI?'openai':'evidence_brief');report.summary={method:summary.method,generatedByAI:summary.generatedByAI,citations:summary.citations.length};mark('Public analysis explanation contains sources and correctly identifies AI versus evidence-only generation');
 for(const path of ['/api/ledger','/api/conversations','/api/contracts','/api/account','/api/records','/api/simulations']){const privateResponse=await call(path);assert.equal(privateResponse.status,401,'Private records must still require a secure app identity: '+path);}
 mark('Personal finances, saved forecasts, private simulations and conversation history remain protected');
 const reopened=await call('/api/nfl/games/'+encodeURIComponent(game.id));assert.equal(reopened.status,200);assert.equal(reopened.data.analysis.id,detail.analysis.id);assertPublicGameDetail(reopened.data,{completed:true});mark('Another identity-free request reopens the saved shared research without a personal session');
 report.status='passed';report.finishedAt=new Date().toISOString();report.limitations=['Acceptance verifies actual data retrieval, football mechanics, public caching and private-record boundaries; it does not prove calibration or market advantage.','Unavailable injury and price data must remain labeled unavailable. Evidence-only text is not a live OpenAI response.','Physical Safari Add to Home Screen installation is not performed by this script.'];write();console.log(JSON.stringify({status:'passed',checks:report.checks.length,report:target,gameId:game.id}));
}catch(error){report.status='failed';report.finishedAt=new Date().toISOString();report.error=error instanceof Error?error.message:'Unknown guest acceptance failure';write();console.error(JSON.stringify({status:'failed',passedChecks:report.checks.length,error:report.error,report:target}));process.exitCode=1;}
