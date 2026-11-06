/** Real disposable-account API/browser tests. Private stdin; no model workloads.
 * Only provisioned qa-render-* @example.test accounts are accepted.
 * "reopen" requires state from a completed initial run and performs no writes.
 */
import {createInterface} from 'node:readline';
import {randomUUID} from 'node:crypto';
import {mkdirSync,writeFileSync,readFileSync} from 'node:fs';
import assert from 'node:assert/strict';
import {chromium,devices} from '@playwright/test';
const base='https://gridiron-ai-frontend.onrender.com',directory='artifacts/render-migration-v24/followup';mkdirSync(directory,{recursive:true});
const input=createInterface({input:process.stdin});console.log('Disposable Auth verifier ready for private stdin configuration.');
input.once('line',async line=>{let browser;const checks=[];const mark=name=>{checks.push({name,status:'passed'});};
 try{
  const values=JSON.parse(line),accounts=values.accounts;
  assert.equal(values.approvedDisposable,true);assert.ok(Array.isArray(accounts)&&accounts.length===2);
  assert.ok(accounts.every(a=>/^qa-render-[a-z0-9-]+@example\.test$/.test(a.email)&&typeof a.password==='string'&&a.password.length>=24));
  browser=await chromium.launch({...(process.env.HTTPS_PROXY?{proxy:{server:process.env.HTTPS_PROXY}}:{})});
  const contexts=await Promise.all(accounts.map(()=>browser.newContext(devices['iPhone 13'])));
  const call=async(ctx,path,body,method=body===undefined?'GET':'POST')=>{const r=await ctx.request.fetch(base+path,{method,headers:{Origin:base,'Content-Type':'application/json'},data:body,timeout:45000});const v=await r.json();return{status:r.status(),data:v};};
  const ok=async(ctx,path,body,method)=>{const r=await call(ctx,path,body,method);assert.ok(r.status>=200&&r.status<300,'Unexpected API status at '+path+': '+r.status);return r.data;};
  for(let i=0;i<2;i++){const r=await ok(contexts[i],'/api/auth',{action:'login',...accounts[i]});assert.equal(r.user.id,accounts[i].id);const cookies=(await contexts[i].cookies(base)).filter(c=>c.name.startsWith('gridiron_sb_'));assert.equal(cookies.length,2);assert.ok(cookies.every(c=>c.secure&&c.httpOnly&&c.sameSite==='Lax'));}mark('Real password login and Secure/HttpOnly session cookies for both QA identities');
  const [a,b]=contexts;let state;
  if(values.mode==='reopen')state=JSON.parse(readFileSync(directory+'/auth-private-state.json','utf8'));
  else{
   const initial=await ok(a,'/api/cloud/ledger');assert.equal(initial.summary.cashBalanceCents,0,'Only an empty new QA wallet may be modified.');assert.equal((await ok(b,'/api/cloud/ledger')).summary.cashBalanceCents,0);
   const run=randomUUID();for(const row of [{type:'starting_balance',amount:'100.00'},{type:'deposit',amount:'50.00'},{type:'withdrawal',amount:'20.00'}])await ok(a,'/api/cloud/ledger',{...row,sportsbook:'DraftKings',reference:'SYNTHETIC-render-'+run+'-'+row.type,note:'SYNTHETIC migration acceptance only'});
   const bet=await ok(a,'/api/cloud/bets',{action:'place',sportsbook:'DraftKings',event:'SYNTHETIC migration acceptance',market:'Manual record test',selection:'SYNTHETIC',stake:'10.00',odds:-110,notes:'No wager was placed externally.'});
   await ok(a,'/api/cloud/bets',{action:'settle',id:bet.id,result:'won',payout:'19.00'});mark('Actual Supabase deposits/withdrawals/recorded wager/settlement');
   const workspace={id:randomUUID(),mutationId:randomUUID(),expectedRevision:0,sport:'NFL',kind:'research',data:{name:'SYNTHETIC migration research',notes:'Storage test; no model output',legs:[],amount:'0',multiplier:'0',fees:'0',pricingBasis:'user_hypothetical',body:'SYNTHETIC account storage verification'}};
   assert.equal((await ok(a,'/api/nfl/workspaces',workspace)).record.revision,1);workspace.expectedRevision=1;workspace.mutationId=randomUUID();workspace.data.notes='SYNTHETIC updated storage test';assert.equal((await ok(a,'/api/nfl/workspaces',workspace)).record.revision,2);
   const conversation=(await ok(a,'/api/cloud/conversations',{title:'SYNTHETIC migration persistence'})).conversation;
   await ok(a,'/api/cloud/conversations/'+conversation.id,{role:'user',content:'SYNTHETIC storage verification, not an AI-generated response.'});
   await ok(a,'/api/cloud/preferences',{preferences:{migrationQaRun:run}});
   state={workspace,conversationId:conversation.id,run,ownerIds:accounts.map(x=>x.id),cashCents:13900,realizedPlCents:900};writeFileSync(directory+'/auth-private-state.json',JSON.stringify(state),{mode:0o600});mark('Research revision, conversation and preference write paths');
  }
  assert.deepEqual(state.ownerIds,accounts.map(x=>x.id));
  const ledger=await ok(a,'/api/cloud/ledger');assert.equal(ledger.summary.cashBalanceCents,13900);assert.equal(ledger.summary.realizedPlCents,900);assert.equal(ledger.summary.pendingExposureCents,0);assert.equal((await ok(b,'/api/cloud/ledger')).summary.cashBalanceCents,0);mark('Exact financial reconciliation; cash movements excluded from betting P/L');
  const own=(await ok(a,'/api/nfl/workspaces?id='+state.workspace.id)).records;assert.equal(own.length,1);assert.equal(own[0].revision,2);assert.equal((await ok(a,'/api/nfl/workspaces?id='+state.workspace.id+'&versions=1')).records.length,2);
  assert.equal((await ok(b,'/api/nfl/workspaces?id='+state.workspace.id)).records.length,0);assert.equal((await call(b,'/api/nfl/workspaces',{...state.workspace,mutationId:randomUUID(),expectedRevision:2})).status,403);assert.equal((await call(b,'/api/cloud/conversations/'+state.conversationId)).status,404);mark('Cross-user read/write isolation');
  await a.clearCookies({name:'gridiron_sb_access'});assert.equal((await ok(a,'/api/auth')).user.id,accounts[0].id);assert.ok((await a.cookies(base)).some(c=>c.name==='gridiron_sb_access'));mark('Refresh-cookie-only session recovery');
  const page=await a.newPage();await page.goto(base+'/#wallet',{waitUntil:'networkidle'});await page.screenshot({path:directory+'/authenticated-qa-wallet.png',fullPage:true});
  const replay=await browser.newContext();await replay.addCookies(await a.cookies(base));await ok(a,'/api/auth',{action:'logout'});assert.equal((await call(a,'/api/cloud/ledger')).status,401);assert.ok([401,403].includes((await call(replay,'/api/cloud/ledger')).status));mark('Logout clears session and revoked session cannot read financial records');
  await a.close();const reopened=await browser.newContext();await ok(reopened,'/api/auth',{action:'login',...accounts[0]});assert.equal((await ok(reopened,'/api/cloud/ledger')).summary.cashBalanceCents,13900);assert.equal((await ok(reopened,'/api/nfl/workspaces?id='+state.workspace.id)).records[0].revision,2);assert.equal((await ok(reopened,'/api/cloud/preferences')).preferences.migrationQaRun,state.run);assert.ok((await ok(reopened,'/api/cloud/conversations/'+state.conversationId)).conversation);mark('Records persist in a newly opened authenticated browser context');
  await ok(reopened,'/api/auth',{action:'logout'});await ok(b,'/api/auth',{action:'logout'});
  writeFileSync(directory+'/auth-'+(values.mode==='reopen'?'reopen':'initial')+'-results.json',JSON.stringify({checkedAt:new Date().toISOString(),checks,productionRecordsModified:false,qaRecordsRetained:true,aiGenerationTested:false,physicalDeviceTested:false},null,2));console.log(JSON.stringify({checks,qaAccounts:2,passed:true}));
 }catch(error){writeFileSync(directory+'/auth-failure.json',JSON.stringify({checkedAt:new Date().toISOString(),passed:false,errorType:error?.name,completedChecks:checks},null,2));console.error('Disposable authentication check failed; no credentials or account payloads are logged.');process.exitCode=1;}
 finally{await browser?.close();input.close();}
});
