/** Removes only the two pre-provisioned, server-marked disposable V5 QA
 * identities through the normal authenticated deletion path. Never accepts
 * arbitrary identities and never resets public or financial database tables. */
import assert from 'node:assert/strict';
import {readFileSync,statSync,writeFileSync} from 'node:fs';
import {EnvHttpProxyAgent,setGlobalDispatcher} from 'undici';
if(process.env.HTTPS_PROXY||process.env.HTTP_PROXY||process.env.https_proxy||process.env.http_proxy)setGlobalDispatcher(new EnvHttpProxyAgent());
assert.equal(process.env.QA_ALLOW_DISPOSABLE_ACCOUNT_DELETION,'1','Explicitly authorize removal of these isolated QA identities.');
const base=new URL(process.env.BASE_URL||'https://gridiron-ai-gray.vercel.app');assert.equal(base.protocol,'https:');
const credentialPath=process.env.QA_CREDENTIALS_FILE||'/tmp/gridiron-v5-qa.json';assert.equal(statSync(credentialPath).mode&0o077,0);
const fixture=JSON.parse(readFileSync(credentialPath,'utf8'));assert.equal(fixture.marker,'gridiron-v5-production-verification');assert.equal(fixture.accounts?.length,2);
for(const path of ['docs/reports/v5-production-private-workflow.json','docs/reports/v5-production-private-browser.json','docs/reports/v5-production-private-webkit-browser.json']){
 const report=JSON.parse(readFileSync(path,'utf8'));assert.equal(report.status,'passed');assert.equal(report.baseUrl,base.origin);
}
process.loadEnvFile('.env.local');
const supabase=new URL(process.env.SUPABASE_URL),publishable=process.env.SUPABASE_PUBLISHABLE_KEY;assert.equal(supabase.hostname,'qdtdjbapdipopncklsdb.supabase.co');assert.ok(publishable&&!publishable.startsWith('sb_secret_'));
const report={status:'running',startedAt:new Date().toISOString(),baseUrl:base.origin,scope:'Exactly two pre-provisioned, server-marked disposable V5 QA identities',credentialsIncluded:false,realUserDataChanged:false,checks:[]};
const output='docs/reports/v5-production-qa-cleanup.json',mark=name=>{report.checks.push({name,status:'passed'});console.log(JSON.stringify({check:name,status:'passed'}));};
const clients=[];
function client(account){
 const jar=new Map();return{account,jar,async call(path,body,method=body===undefined?'GET':'POST'){
  const response=await fetch(new URL('/api/'+path,base),{method,headers:{Origin:base.origin,'Content-Type':'application/json',Cookie:[...jar].map(([k,v])=>k+'='+v).join('; ')},body:body===undefined?undefined:JSON.stringify(body),signal:AbortSignal.timeout(90000),redirect:'manual',cache:'no-store'});
  assert.equal(response.headers.get('location'),null);
  const incoming=response.headers.getSetCookie();for(const value of incoming){const first=value.split(';')[0],at=first.indexOf('=');jar.set(first.slice(0,at),first.slice(at+1));}
  const text=await response.text();let data;try{data=JSON.parse(text);}catch{data=null;}return{status:response.status,data};
 }};
}
try{
 for(const account of fixture.accounts){
  assert.match(account.id,/^[a-f0-9-]{36}$/);assert.ok(account.email.startsWith('gridiron-v5-production-qa-')&&account.email.endsWith('@example.test'));
  const scoped=client(account),logged=await scoped.call('auth',{action:'login',email:account.email,password:account.password});assert.equal(logged.status,200,logged.data?.error);assert.equal(logged.data.user.id,account.id);
  const token=decodeURIComponent(scoped.jar.get('gridiron_sb_access'));assert.ok(token&&token!=='undefined');
  const verified=await fetch(new URL('/auth/v1/user',supabase),{headers:{apikey:publishable,Authorization:'Bearer '+token},signal:AbortSignal.timeout(30000)});assert.equal(verified.status,200);const identity=await verified.json();
  assert.equal(identity.id,account.id);assert.equal(identity.email,account.email);assert.equal(identity.app_metadata?.gridiron_qa_marker,fixture.marker,'Refusing deletion without an exact server-controlled QA marker.');
  clients.push(scoped);
 }
 mark('Both exact UUIDs and reserved test emails match the server-controlled QA marker before any deletion');
 for(const scoped of clients){
  const oldCookies=new Map(scoped.jar),removed=await scoped.call('account',{confirmation:'DELETE'},'DELETE');assert.equal(removed.status,200,removed.data?.error);assert.equal(removed.data.deleted,true);
  const replay=await fetch(new URL('/api/ledger',base),{headers:{Origin:base.origin,Cookie:[...oldCookies].map(([k,v])=>k+'='+v).join('; ')},signal:AbortSignal.timeout(30000)});assert.equal(replay.status,401,'A deleted QA identity must not retain access through its old session.');
  const oldToken=decodeURIComponent(oldCookies.get('gridiron_sb_access'));
  const identity=await fetch(new URL('/auth/v1/user',supabase),{headers:{apikey:publishable,Authorization:'Bearer '+oldToken},signal:AbortSignal.timeout(30000)});assert.ok([401,403].includes(identity.status));
  const retry=await scoped.call('auth',{action:'login',email:scoped.account.email,password:scoped.account.password});assert.ok([400,401,403].includes(retry.status));
 }
 mark('Only the two authenticated QA owners are deleted through the session-revoking Edge Function');
 mark('Old sessions and passwords cannot reopen either removed test identity');
 const publicResponse=await fetch(new URL('/api/nfl',base),{signal:AbortSignal.timeout(30000)});assert.equal(publicResponse.status,200);assert.ok((await publicResponse.json()).games.length>0);mark('Shared real NFL research remains available after isolated QA cleanup');
 report.status='passed';report.finishedAt=new Date().toISOString();report.limitations=['Aggregate SQL verification of the unchanged non-QA identity and removal of all QA-owned rows is recorded separately by the operator.'];
}catch(error){report.status='failed';report.finishedAt=new Date().toISOString();report.error=error instanceof Error?error.message:'Disposable QA cleanup failed';process.exitCode=1;}
finally{writeFileSync(output,JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify({status:report.status,checks:report.checks.length,report:output,...(report.error?{error:report.error}:{})}));}
