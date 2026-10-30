/** Sequential production mode verification using the fitted model already
 * saved by smoke-pwa-workflow.mjs. No financial writes or new fit is performed. */
import {readFileSync,writeFileSync,mkdirSync,statSync} from 'node:fs';
import {dirname} from 'node:path';
import assert from 'node:assert/strict';
import {EnvHttpProxyAgent,setGlobalDispatcher} from 'undici';
import {runSavedSimulation,validateCompleteGameResult} from './lib/simulation-workflow.mjs';

if(process.env.HTTPS_PROXY||process.env.HTTP_PROXY||process.env.https_proxy||process.env.http_proxy)setGlobalDispatcher(new EnvHttpProxyAgent());
const base=new URL(process.env.BASE_URL||'http://127.0.0.1:3000');
if(base.protocol!=='https:'&&!['localhost','127.0.0.1'].includes(base.hostname))throw Error('Production checks require HTTPS.');
if(process.env.QA_ALLOW_SYNTHETIC_WRITES!=='1')throw Error('Explicit disposable QA account authorization is required.');
const credentialsPath=process.env.QA_CREDENTIALS_FILE||'/tmp/gridiron-production-qa.json';
assert.equal(statSync(credentialsPath).mode&0o077,0,'QA credentials must remain private to their owner.');
const credentials=JSON.parse(readFileSync(credentialsPath,'utf8')),accounts=Array.isArray(credentials)?credentials:credentials.accounts;
assert.ok(accounts?.length>=2);for(const account of accounts.slice(0,2))assert.ok(account.id&&/qa/i.test(account.email)&&account.email.endsWith('@example.test'));
const previous=JSON.parse(readFileSync(process.env.QA_WORKFLOW_REPORT_PATH||'docs/reports/pwa-production-workflow.json','utf8'));
assert.equal(previous.baseUrl,base.origin,'The prerequisite report must refer to this deployment origin.');assert.ok(previous.fittedModelId&&previous.simulationId,'Run the 10,000-game smoke workflow first.');
const outputPath=process.env.QA_MODES_REPORT_PATH||'docs/reports/pwa-production-simulation-modes.json';
const report={status:'running',startedAt:new Date().toISOString(),baseUrl:base.origin,fittedModelId:previous.fittedModelId,existingTenThousandSimulationId:previous.simulationId,source:'Actual normalized historical NFL play-by-play from the prerequisite fitted model; not live projections or fabricated injury evidence.',runs:[],financialWrites:false,credentialsIncluded:false,physicalIphoneInstallationTested:false};
const writeReport=()=>{mkdirSync(dirname(outputPath),{recursive:true});writeFileSync(outputPath,JSON.stringify(report,null,2)+'\n');};

function session(account){
 const cookies=new Map();return{async call(path,body,method=body===undefined?'GET':'POST'){
  const response=await fetch(new URL('/api/'+path,base),{method,headers:{Origin:base.origin,'Content-Type':'application/json',Cookie:[...cookies].map(([key,value])=>`${key}=${value}`).join('; ')},body:body===undefined?undefined:JSON.stringify(body),signal:AbortSignal.timeout(300000)});
  for(const value of response.headers.getSetCookie()){const first=value.split(';')[0],at=first.indexOf('=');cookies.set(first.slice(0,at),first.slice(at+1));}
  const raw=await response.text();let data;try{data=JSON.parse(raw);}catch{data=null;}return{status:response.status,data,response};
 },async login(){assert.equal((await this.call('backend',{backend:'supabase'})).status,200);const result=await this.call('auth',{action:'login',email:account.email,password:account.password});assert.equal(result.status,200,result.data?.error);assert.equal(result.data.user.id,account.id);assert.match(result.response.headers.get('set-cookie')||'',/HttpOnly/);if(base.protocol==='https:')assert.match(result.response.headers.get('set-cookie')||'',/Secure/);}};
}

try{
 const client=session(accounts[0]);await client.login();
 const ledger=(await client.call('ledger')).data.summary;
 const fitted=(await client.call('simulations?id='+previous.fittedModelId)).data?.job;
 assert.equal(fitted.status,'completed');assert.equal(fitted.kind,'fit');assert.equal(fitted.provenanceVerified,true);assert.ok(fitted.result.model?.sha256);
 const original=(await client.call('simulations?id='+previous.simulationId)).data?.job;assert.equal(original.status,'completed');assert.equal(original.provenanceVerified,true);validateCompleteGameResult(original.result,10000);
 const bootstrap=original.result.uncertainty.parameterBootstrap;
 for(const count of [50000,100000]){
  const started=Date.now();const run=await runSavedSimulation(client,{action:'simulate',modelJobId:previous.fittedModelId,home:original.result.home,away:original.result.away,eventStart:original.result.eventStart,simulations:count,seed:original.result.seed,representativeGames:1,injuryEntityKeys:[],...(bootstrap?{parameterUncertainty:{replicates:bootstrap.replicates,gamesPerReplicate:bootstrap.gamesPerReplicate}}:{}),contracts:original.result.contracts.map(contract=>contract.settlement)},{deadlineMs:Number(process.env.QA_SIMULATION_DEADLINE_MS)||600000,onProgress:value=>console.log(JSON.stringify({simulationJob:value.id,status:value.status,completeGamesRequested:count}))});
  assert.equal(run.status,'completed',run.error);const validation=validateCompleteGameResult(run.result,count);
  assert.equal(run.result.inputDataVersion,original.result.inputDataVersion);assert.equal(run.result.seed,original.result.seed);
  assert.deepEqual(run.result.representativeGames[0],original.result.representativeGames[0],'Reproducible seeds must preserve the first full game as count increases.');
  if(bootstrap)assert.deepEqual(run.result.uncertainty.parameterBootstrap,bootstrap,'Increasing base simulation count must not manufacture narrower parameter uncertainty.');
  report.runs.push({id:run.id,status:'passed',elapsedMilliseconds:Date.now()-started,...validation,independentParameterUncertaintyUnchanged:bootstrap?true:null});writeReport();
  console.log(JSON.stringify({check:'Production complete-game mode verified',completeGames:count,status:'passed',id:run.id}));
 }
 const fresh=session(accounts[0]);await fresh.login();
 for(const run of report.runs){const reopened=(await fresh.call('simulations?id='+run.id)).data?.job;assert.equal(reopened.status,'completed');assert.equal(reopened.provenanceVerified,true);validateCompleteGameResult(reopened.result,run.completeGames);}
 assert.deepEqual((await fresh.call('ledger')).data.summary,ledger,'Simulation mode checks may not alter account finances.');
 const other=session(accounts[1]);await other.login();assert.equal((await other.call('simulations?id='+report.runs[0].id)).status,404,'Another owner must not retrieve saved simulation results.');
 report.status='passed';report.finishedAt=new Date().toISOString();report.freshSessionReadback=true;report.crossOwnerAccessRejected=true;report.financialSummaryUnchanged=true;report.limitations=['Complete-game mechanics, reproducibility and persistence checks do not establish forecast calibration or market superiority.','Current historical input lacks verified availability labels; injury-adjusted projections remain withheld without evidence.','The parameter bootstrap is a separate uncertainty estimate, with finite inner simulation noise; structural uncertainty remains unestimated.'];writeReport();console.log(JSON.stringify({status:'passed',report:outputPath,runs:report.runs.length}));
}catch(error){report.status='failed';report.finishedAt=new Date().toISOString();report.error=error instanceof Error?error.message:'Unknown simulation mode verification failure';writeReport();console.error(JSON.stringify({status:'failed',error:report.error,report:outputPath}));process.exitCode=1;}
