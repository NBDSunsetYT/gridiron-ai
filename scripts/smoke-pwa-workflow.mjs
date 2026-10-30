/** Production/local workflow check against explicitly provisioned disposable QA
 * accounts. No account registration, emails, account deletion or real wager
 * execution. Every test market/financial row is visibly SYNTHETIC.
 *
 * BASE_URL=https://actual-app.example QA_CREDENTIALS_FILE=/private/qa.json
 * QA_ALLOW_SYNTHETIC_WRITES=1 node scripts/smoke-pwa-workflow.mjs
 * Optional: PBP_NORMALIZED_CSV, PBP_SOURCE, PBP_AS_OF, PBP_EVENT_START for a real
 * historical fit + 10,000 complete games. A missing service/feed is not a pass.
 */
import {readFileSync,writeFileSync,mkdirSync} from 'node:fs';
import {randomUUID} from 'node:crypto';
import assert from 'node:assert/strict';
import {EnvHttpProxyAgent,setGlobalDispatcher} from 'undici';
import {runSavedSimulation,receiverFromNormalizedCsv,validateCompleteGameResult} from './lib/simulation-workflow.mjs';

// Preserve the managed environment's proxy/CA policy while keeping NO_PROXY
// loopback requests local. Never disable TLS verification for a production test.
if(process.env.HTTPS_PROXY||process.env.HTTP_PROXY||process.env.https_proxy||process.env.http_proxy)setGlobalDispatcher(new EnvHttpProxyAgent());

const base=new URL(process.env.BASE_URL||'http://127.0.0.1:3000');
if(base.protocol!=='https:'&&!['localhost','127.0.0.1'].includes(base.hostname))throw Error('Production checks require HTTPS.');
if(process.env.QA_ALLOW_SYNTHETIC_WRITES!=='1')throw Error('Explicitly set QA_ALLOW_SYNTHETIC_WRITES=1 for empty disposable QA accounts only.');
const credentials=JSON.parse(readFileSync(process.env.QA_CREDENTIALS_FILE||'/tmp/gridiron-pwa-qa.json','utf8'));
const accounts=Array.isArray(credentials)?credentials:credentials.accounts;
assert.ok(Array.isArray(accounts)&&accounts.length>=2,'Two pre-provisioned disposable QA accounts are required.');
for(const a of accounts.slice(0,2))assert.ok(a.id&&/qa/i.test(a.email)&&a.email.endsWith('@example.test'),'Only generated QA identities at example.test are supported.');
const checks=[],unavailable=[];
const mark=name=>{checks.push({name,status:'passed'});console.log(JSON.stringify({check:name,status:'passed'}));};
function session(account){const cookies=new Map();return{account,async call(path,body,method=body===undefined?'GET':'POST'){
 const response=await fetch(new URL('/api/'+path,base),{method,headers:{Origin:base.origin,'Content-Type':'application/json',Cookie:[...cookies].map(([k,v])=>`${k}=${v}`).join('; ')},body:body===undefined?undefined:JSON.stringify(body),signal:AbortSignal.timeout(path==='simulations'?300000:90000)});
 for(const value of response.headers.getSetCookie()){const first=value.split(';')[0],at=first.indexOf('=');cookies.set(first.slice(0,at),first.slice(at+1));}
 const text=await response.text();let data;try{data=JSON.parse(text);}catch{data=text;}
 return{response,status:response.status,data};
 },async login(){const routed=await this.call('backend',{backend:'supabase'});assert.equal(routed.status,200);const result=await this.call('auth',{action:'login',email:account.email,password:account.password});assert.equal(result.status,200,result.data?.error);assert.equal(result.data.user.id,account.id);assert.match(result.response.headers.get('set-cookie')||'',/HttpOnly/);return result;}};}
const a=session(accounts[0]),b=session(accounts[1]);
try{
 const anonymous=await a.call('ledger');assert.equal(anonymous.status,401);mark('Anonymous financial access rejected');
 const manifestResponse=await fetch(new URL('/manifest.webmanifest',base));assert.equal(manifestResponse.status,200);const manifest=await manifestResponse.json();assert.equal(manifest.display,'standalone');for(const size of ['192x192','512x512']){const icon=manifest.icons.find(i=>i.sizes===size);assert.ok(icon,`Missing ${size} icon`);assert.equal((await fetch(new URL(icon.src,base))).status,200);}mark('Public standalone manifest and required icons reachable');
 await a.login();await b.login();const before=(await a.call('ledger')).data;assert.equal(before.summary.cashBalanceCents,0,'Refusing to write to a nonempty account.');assert.equal((await b.call('ledger')).data.summary.cashBalanceCents,0);mark('Real Supabase login and two isolated empty QA accounts');
 for(const row of [{type:'starting_balance',amount:'500.00'},{type:'deposit',amount:'100.00'},{type:'withdrawal',amount:'150.00'}]){const r=await a.call('ledger',{...row,sportsbook:'DraftKings',note:'SYNTHETIC PWA WORKFLOW TEST ONLY',reference:'SYNTHETIC-PWA-'+randomUUID()});assert.equal(r.status,201,r.data?.error);}
 const placed=await a.call('bets',{action:'place',sportsbook:'DraftKings',event:'SYNTHETIC TEST EVENT',market:'SYNTHETIC TEST MARKET',selection:'SYNTHETIC TEST SELECTION',odds:-110,stake:'100.00'});assert.equal(placed.status,201,placed.data?.error);assert.equal((await a.call('ledger')).data.summary.pendingExposureCents,10000);const settled=await a.call('bets',{action:'settle',id:placed.data.id,result:'won',payout:'175.00'});assert.equal(settled.status,201,settled.data?.error);
 let ledger=(await a.call('ledger')).data;assert.equal(ledger.summary.cashBalanceCents,52500);assert.equal(ledger.summary.realizedPlCents,7500);assert.equal(ledger.summary.totalDepositsCents,10000);assert.equal(ledger.summary.totalWithdrawalsCents,15000);assert.equal(ledger.summary.pendingExposureCents,0);assert.equal((await b.call('ledger')).data.summary.cashBalanceCents,0);mark('Exact ledger arithmetic, settlement and account isolation');
 const quote=await a.call('contracts',{action:'quote',contractId:'SYNTHETIC-MANUAL-PWA-'+randomUUID(),eventId:'SYNTHETIC-QA-EVENT',event:'SYNTHETIC QA event — not a live NFL listing',question:'SYNTHETIC manual binary contract: total strictly greater than 45.5?',threshold:45.5,operator:'gt',eventStart:new Date(Date.now()+86400000).toISOString(),settlementRule:'SYNTHETIC arithmetic test: YES iff total >45.5; equality settles NO.',rulesUrl:'https://example.invalid/synthetic-rules',yesAskCents:'52',noAskCents:'50',quotedAt:new Date(Date.now()-1000).toISOString(),sourceUrl:'https://example.invalid/synthetic-manual-quote',verified:true,entryFeeCents:'1',winFeeCents:'0',feeSource:'SYNTHETIC fee arithmetic fixture, not an actual DraftKings fee'});assert.equal(quote.status,201,quote.data?.error);
 // Exactly half of these explicitly synthetic mechanical outcomes are YES;
 // this is a storage/fee test, never represented as an NFL forecast.
 const samples=Array.from({length:20},(_,i)=>i>=10),probability=samples.filter(Boolean).length/samples.length;
 const forecast=await a.call('contracts',{action:'predict',quoteId:quote.data.quote.id,probability,side:'YES',quantity:2,asOf:new Date().toISOString(),inputsHash:'SYNTHETIC-PWA-MECHANICAL-TEST',modelVersion:'SYNTHETIC-STORAGE-TEST-ONLY',evidence:{source:'SYNTHETIC 10 YES /20 mechanical outcomes; not NFL evidence',method:'SYNTHETIC persistence/fee test only',sampleSize:samples.length}});assert.equal(forecast.status,201,forecast.data?.error);assert.equal(forecast.data.prediction.valuation.costCents,'106');assert.equal(forecast.data.prediction.sourceValidation,'user_supplied_model_estimate_not_independently_verified');
 const paper=await a.call('contracts',{action:'paper',predictionId:forecast.data.prediction.id});assert.equal(paper.status,201,paper.data?.error);assert.equal((await a.call('ledger')).data.summary.cashBalanceCents,52500);mark('Clearly synthetic manually imported binary contract, fee calculation, saved prediction and cash-separated paper position');
 const now=Date.now();const injuryInput={entityKey:'SYNTHETIC-QA-PLAYER',player:'SYNTHETIC QA PLAYER',team:'SYNTHETIC QA TEAM',status:'questionable',publicationAt:new Date(now-5000).toISOString(),checkedAt:new Date(now-3000).toISOString(),sourceUrl:'https://www.nfl.com/injuries/',sourceName:'SYNTHETIC citation mechanics test; no actual player injury claimed',sourceType:'official',verified:true,note:'SYNTHETIC isolated QA record only. No real player designation or news is claimed.'};const uncertain=await a.call('injuries',injuryInput);assert.equal(uncertain.status,201,uncertain.data?.error);assert.equal(uncertain.data.record.availability,null);const confirmed=await a.call('injuries',{...injuryInput,status:'out',checkedAt:new Date(now-1000).toISOString()});assert.equal(confirmed.status,201,confirmed.data?.error);assert.deepEqual([confirmed.data.record.availability.active,confirmed.data.record.availability.limited,confirmed.data.record.availability.out],[0,0,1]);mark('Uncertain availability is withheld without cohorts; confirmed synthetic designation stays distinct');
 const conversation=await a.call('conversations',{title:'SYNTHETIC PWA workflow research'});assert.equal(conversation.status,201,conversation.data?.error);const conversationId=conversation.data.conversation.id;assert.equal((await a.call('conversations/'+conversationId,{role:'user',content:'SYNTHETIC saved research question; no model answer invented.'})).status,201);assert.equal((await b.call('conversations/'+conversationId)).status,404);mark('Persistent conversation and cross-owner access rejection');
 const warehouse=await a.call('warehouse',{action:'sync_games',seasonFrom:2023,seasonTo:2023});assert.equal(warehouse.status,200,warehouse.data?.error);const history=await a.call('warehouse?kind=games&limit=300');assert.equal(history.status,200,history.data?.error);assert.ok((history.data.records??history.data.rows??[]).length>0,'Expected actual imported NFL games');mark('Actual public NFL historical schedule loaded');
 let simulationId=null,fittedModelId=null,simulationVerification=null;
 if(process.env.PBP_NORMALIZED_CSV){
  const csv=readFileSync(process.env.PBP_NORMALIZED_CSV,'utf8');
  const simulationOptions={deadlineMs:Number(process.env.QA_SIMULATION_DEADLINE_MS)||600000,onProgress:value=>console.log(JSON.stringify({simulationJob:value.id,status:value.status}))};
  const fitted=await runSavedSimulation(a,{action:'fit',csv,source:process.env.PBP_SOURCE||'https://github.com/nflverse/nflverse-data/releases/tag/pbp ; actual historical replay; publication availability unknown',asOf:process.env.PBP_AS_OF||'2023-11-30T00:00:00Z',options:{recencyHalfLifeDays:180,conditionalShrinkage:true,strictAvailability:false}},simulationOptions);
  assert.equal(fitted.status,'completed',fitted.error);assert.ok(fitted.result.model?.sha256,'A fitted evidence artifact is required.');fittedModelId=fitted.id;
  const run=await runSavedSimulation(a,{action:'simulate',modelJobId:fitted.id,home:'DAL',away:'SEA',eventStart:process.env.PBP_EVENT_START||'2023-12-01T01:15:00Z',simulations:10000,seed:2026,representativeGames:1,injuryEntityKeys:[],...(process.env.QA_PARAMETER_BOOTSTRAP==='0'?{}:{parameterUncertainty:{replicates:10,gamesPerReplicate:100}}),contracts:[{id:'HISTORICAL-QA-TOTAL-45.5',kind:'total',threshold:45.5,direction:'over',equality:'no'}]},simulationOptions);
  assert.equal(run.status,'completed',run.error);simulationVerification=validateCompleteGameResult(run.result,10000);
  simulationId=run.id;mark('Actual historical fitted model produced 10,000 coherent complete games and a saved replay');
  const playerId=fitted.result.model.rows?.find(r=>['DAL','SEA'].includes(r.o)&&r.receiver)?.receiver??receiverFromNormalizedCsv(csv,['DAL','SEA']);
  if(playerId){
   // This input deliberately has no historical availability labels. Neither
   // queued nor synchronous service mode may invent an injury adjustment.
   const unsupportedInput={action:'simulate',modelJobId:fitted.id,home:'DAL',away:'SEA',eventStart:process.env.PBP_EVENT_START||'2023-12-01T01:15:00Z',simulations:10000,scenario:{playerId,status:'inactive'}};
   const submitted=await a.call('simulations',unsupportedInput);
   if(submitted.status===422){assert.match(submitted.data?.error??'',/evidence|scenario/i);}
   else{
    assert.ok([200,202].includes(submitted.status),submitted.data?.error);let replayed=false;
    const client={call:(...args)=>{if(!replayed){replayed=true;return Promise.resolve(submitted);}return a.call(...args);}};
    const unsupported=await runSavedSimulation(client,unsupportedInput,simulationOptions);
    assert.ok(['failed','blocked'].includes(unsupported.status),'Unsupported injury assumptions must not produce a completed projection.');assert.match(unsupported.error,/evidence|scenario/i);
   }
   mark('Unsupported player-availability adjustment is blocked instead of guessing an injury multiplier');
  }else unavailable.push({feature:'Unsupported player-availability request check',reason:'No receiver ID present in supplied normalized evidence; no identity was invented.'});
 }else unavailable.push({feature:'Production 10,000-game modeling run',reason:'PBP_NORMALIZED_CSV not supplied; no substitute simulation was invented.'});
 const reopened=session(accounts[0]);await reopened.login();assert.equal((await reopened.call('ledger')).data.summary.cashBalanceCents,52500);assert.ok((await reopened.call('contracts')).data.predictions.some(p=>p.id===forecast.data.prediction.id));assert.equal((await reopened.call('conversations/'+conversationId)).data.conversation.messages[0].role,'user');if(simulationId){const saved=(await reopened.call('simulations?id='+simulationId)).data.job;assert.equal(saved.status,'completed');assert.equal(saved.provenanceVerified,true);assert.equal(saved.result.simulations,10000);}mark('Fresh client sign-in reopens remote balances, predictions, conversations and supplied simulations');
 const ai=await a.call('assistant',{messages:[{role:'user',content:'Use the read_ledger tool. What are my total recorded withdrawals and realized P/L? Cite the ledger and do not invent records.'}]});if(ai.status===503){unavailable.push({feature:'Live conversational AI',reason:'Server reports unavailable credentials/service; no fabricated answer accepted.'});}else{assert.equal(ai.status,200,ai.data?.error);assert.ok(typeof ai.data==='string'&&/read_ledger|\[ledger\]/.test(ai.data),'A real ledger citation is required');mark('Live assistant returned a ledger-cited response');}
 ledger=(await a.call('ledger')).data;assert.equal(ledger.summary.cashBalanceCents,52500);assert.equal(ledger.summary.realizedPlCents,7500);
 const report={status:unavailable.length?'passed_with_explicit_unavailable_features':'passed',checkedAt:new Date().toISOString(),baseUrl:base.origin,environment:'Disposable SYNTHETIC QA accounts only; actual public history separated from synthetic financial/contract/injury mechanics',checks,unavailable,simulationId,fittedModelId,simulationVerification,predictionId:forecast.data.prediction.id,conversationId,wagerId:placed.data.id,credentialsIncluded:false,physicalIphoneInstallationTested:false};const path=process.env.QA_REPORT_PATH||'docs/reports/pwa-production-workflow.json';mkdirSync(new URL('../',new URL(path,'file://'+process.cwd()+'/')),{recursive:true});writeFileSync(path,JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify({status:report.status,checks:checks.length,unavailable:unavailable.length,report:path}));
}catch(error){console.error(JSON.stringify({status:'failed',passedChecks:checks.map(c=>c.name),error:error instanceof Error?error.message:'Unknown workflow failure'}));process.exitCode=1;}
