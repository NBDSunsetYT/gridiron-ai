// Read-only production acceptance, plus the no-op missing-configuration analysis
// request. This never supplies prices, creates accounts or records transactions.
import assert from 'node:assert/strict';
import {writeFile,mkdir} from 'node:fs/promises';
import {dirname} from 'node:path';

const base=new URL(process.env.BASE_URL||'https://gridiron-ai-gray.vercel.app');
assert.equal(base.protocol,'https:','Use the deployed HTTPS application.');
const report={startedAt:new Date().toISOString(),baseUrl:base.origin,status:'running',scope:'actual_deployed_missing_source_diagnostics',mockedResponses:false,accountsCreated:false,financialWrites:false,sourcePricesInvented:false,liveDraftKingsContractsVerified:0,checks:[]};
async function read(path,method='GET'){
 const response=await fetch(new URL(path,base),{method,headers:{Accept:'application/json',...(method==='POST'?{Origin:base.origin,'Content-Type':'application/json'}:{})},...(method==='POST'?{body:'{}'}:{}),signal:AbortSignal.timeout(45000),redirect:'error'});
 const body=await response.json();return{response,body};
}
async function check(name,work){await work();report.checks.push({name,status:'passed'});console.log(JSON.stringify({name,status:'passed'}));}
try{
 await check('The actual published application and persistent research dependencies remain reachable',async()=>{
  const{response,body}=await read('/api/health?check=dependencies');assert.equal(response.status,200);assert.equal(body.version,'7.0.1');assert.equal(body.backend,'supabase');assert.equal(body.checks.supabase,'reachable');assert.equal(body.checks.simulations,'reachable');report.health={version:body.version,backend:body.backend,checks:body.checks};
 });
 for(const path of ['/api/nfl/markets','/api/props'])await check(`${path} identifies missing source configuration without claiming an empty NFL inventory or a provider HTTP failure`,async()=>{
  const{response,body}=await read(path);assert.equal(response.status,200);assert.equal(body.status,'unavailable');assert.equal(body.runId,null);assert.equal(body.totalResults,0);
  const source=body.providers.find(value=>value.provider==='DraftKings Predictions');assert.ok(source);assert.equal(source.diagnostic.code,'feed_not_configured');assert.equal(source.diagnostic.stage,'configuration');assert.equal(source.diagnostic.httpStatus,null);assert.equal(source.diagnostic.retryable,false);assert.equal(source.diagnostic.requiresOperator,true);assert.ok(Number.isFinite(Date.parse(source.diagnostic.checkedAt)));assert.equal(source.sourceUrl,'https://predictions.draftkings.com/en/markets/football/nfl');assert.equal(source.contracts,0);assert.equal(body.results.length,0);report.diagnostic=source.diagnostic;
 });
 await check('The real one-tap action returns the same diagnosis without queuing replacement prices or simulations',async()=>{
  const{response,body}=await read('/api/nfl/markets/analyze','POST');assert.equal(response.status,200);assert.equal(body.runId,null);assert.equal(body.resultSetId,null);assert.equal(body.results.length,0);assert.equal(body.providers.find(value=>value.provider==='DraftKings Predictions').diagnostic.code,'feed_not_configured');
 });
 await check('Public NFL games remain available without a database-provider or app login',async()=>{
  const{response,body}=await read('/api/nfl');assert.equal(response.status,200);assert.ok(Array.isArray(body.games));assert.ok(body.games.length>0);report.publicGames=body.games.length;
 });
 for(const path of ['/api/ledger','/api/conversations'])await check(`${path} still requires verified app identity`,async()=>{
  const{response}=await read(path);assert.equal(response.status,401);
 });
 report.status='passed';
 report.limitations=['These live checks verify the actual missing-configuration branch, not an authenticated live vendor feed.','Other source HTTP/mapping/rate-limit branches are tested separately with labeled synthetic transports.','No private user records, confirmation state, database schema or simulation model are changed.','Zero verified live DraftKings contracts does not establish that the platform has no NFL markets.'];
}catch(error){report.status='failed';report.error=error instanceof Error?error.message:String(error);process.exitCode=1;}
finally{
 report.finishedAt=new Date().toISOString();const path=process.env.QA_REPORT_PATH||'docs/reports/draftkings-production-verification.json';await mkdir(dirname(path),{recursive:true});await writeFile(path,JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify({status:report.status,checks:report.checks.length,report:path}));
}
