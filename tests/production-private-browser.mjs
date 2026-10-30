/** Read-only iPhone-sized app identity acceptance after the isolated private API
 * workflow. No account creation, emails, finances, records or model mutations. */
import assert from 'node:assert/strict';
import {readFileSync,statSync,mkdirSync,writeFileSync} from 'node:fs';
import {dirname} from 'node:path';
import {chromium,webkit,devices,expect} from '@playwright/test';
const base=new URL(process.env.BASE_URL||'https://gridiron-ai-gray.vercel.app');assert.equal(base.protocol,'https:');
const credentialPath=process.env.QA_CREDENTIALS_FILE||'/tmp/gridiron-v5-qa.json';assert.equal(statSync(credentialPath).mode&0o077,0);
const credentials=JSON.parse(readFileSync(credentialPath,'utf8')),account=credentials.accounts?.[0];assert.equal(credentials.marker,'gridiron-v5-production-verification');assert.ok(account?.id&&account.email.endsWith('@example.test'));
const previous=JSON.parse(readFileSync(process.env.QA_WORKFLOW_REPORT_PATH||'docs/reports/v5-production-private-workflow.json','utf8'));assert.equal(previous.status,'passed');assert.equal(previous.baseUrl,base.origin);assert.ok(previous.conversationId);
const expectedBalance=Number(process.env.QA_EXPECTED_BALANCE_CENTS||52500),expectedPl=Number(process.env.QA_EXPECTED_PL_CENTS||7500);
const proxyValue=process.env.HTTPS_PROXY||process.env.https_proxy||process.env.HTTP_PROXY||process.env.http_proxy;
const proxy=proxyValue?(()=>{const u=new URL(proxyValue);return{server:u.origin,...(u.username?{username:decodeURIComponent(u.username)}:{}),...(u.password?{password:decodeURIComponent(u.password)}:{})};})():undefined;
const engine=process.env.QA_BROWSER||'chromium';assert.ok(['chromium','webkit'].includes(engine));
const report={status:'running',startedAt:new Date().toISOString(),baseUrl:base.origin,profile:`iPhone13 ${engine} emulation`,engine,accountsCreated:false,financialWrites:false,researchWrites:false,credentialsIncluded:false,physicalIphoneInstallationTested:false,checks:[]};
const mark=name=>{report.checks.push({name,status:'passed'});console.log(JSON.stringify({check:name,status:'passed'}));};
const output=process.env.QA_REPORT_PATH||'docs/reports/v5-production-private-browser.json';let browser;
try{
 browser=await(engine==='webkit'?webkit:chromium).launch({headless:true,...(proxy?{proxy}:{})});
 const{defaultBrowserType:_,...options}=devices['iPhone 13'];
 for(let attempt=0;attempt<2;attempt++){
  const context=await browser.newContext(options),page=await context.newPage(),errors=[];page.on('pageerror',()=>errors.push('uncaught_browser_exception'));
  await page.goto(new URL('/#bankroll',base).href,{waitUntil:'networkidle',timeout:90000});await page.getByRole('button',{name:'Continue with GRIDIRON AI',exact:true}).click();
  await page.getByLabel('Email',{exact:true}).fill(account.email);await page.getByLabel('Password',{exact:true}).fill(account.password);await page.getByRole('button',{name:'Sign in securely',exact:true}).click();await expect(page.getByRole('dialog')).toHaveCount(0,{timeout:60000});await expect(page.getByRole('button',{name:'Account settings',exact:true})).toBeVisible();assert.equal(new URL(page.url()).origin,base.origin);
  const auth=await(await context.request.get(new URL('/api/auth',base).href)).json();assert.equal(auth.user.id,account.id);
  const cookies=await context.cookies(base.origin);for(const name of ['gridiron_sb_access','gridiron_sb_refresh']){const c=cookies.find(cookie=>cookie.name===name);assert.ok(c?.secure&&c.httpOnly&&c.sameSite==='Lax');}
  const ledgerResponse=await context.request.get(new URL('/api/ledger',base).href);assert.equal(ledgerResponse.status(),200);const ledger=await ledgerResponse.json();assert.equal(ledger.summary.cashBalanceCents,expectedBalance);assert.equal(ledger.summary.realizedPlCents,expectedPl);
  const balance=new Intl.NumberFormat('en-US',{style:'currency',currency:'USD'}).format(expectedBalance/100);await expect(page.locator('main').getByText(balance,{exact:true}).first()).toBeVisible({timeout:30000});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
  mark(attempt===0?'GRIDIRON sign-in opens the real private Wallet with secure cookies':'A fresh browser session reopens the exact same persistent Wallet');
  const listResponse=await context.request.get(new URL('/api/conversations',base).href);assert.equal(listResponse.status(),200);const conversations=(await listResponse.json()).conversations,conversation=conversations.find(value=>value.id===previous.conversationId);assert.ok(conversation);
  const detailResponse=await context.request.get(new URL('/api/conversations/'+conversation.id,base).href);assert.equal(detailResponse.status(),200);const saved=(await detailResponse.json()).conversation;assert.ok(saved.messages.some(message=>message.role==='user')&&saved.messages.some(message=>message.role==='assistant'));
  await page.goto(new URL('/#conversations',base).href,{waitUntil:'networkidle'});await expect(page.getByRole('heading',{name:'Conversations worth keeping.',exact:true})).toBeVisible({timeout:30000});await page.getByRole('button',{name:conversation.title,exact:false}).click();
  const thread=page.getByRole('region',{name:'Saved conversation'});for(const message of saved.messages)if(message.content)await expect(thread).toContainText(String(message.content).slice(0,100));await expect(page.locator('.terminal')).not.toHaveClass(/advanced-mode/);assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));assert.equal(errors.length,0);
  mark(attempt===0?'Saved private game questions and explanations open in the consumer interface':'Another fresh sign-in retains the same private conversation and messages');await context.close();
 }
 report.status='passed';report.finishedAt=new Date().toISOString();report.limitations=['Uses only the explicitly provisioned disposable QA identity and existing synthetic financial fixtures.',`Tests real iPhone-sized ${engine} UI and HTTPS app sessions, not a physical Safari device.`];
}catch(error){report.status='failed';report.finishedAt=new Date().toISOString();report.error=error instanceof Error?error.message:'Unknown private browser acceptance failure';process.exitCode=1;}
finally{await browser?.close();mkdirSync(dirname(output),{recursive:true});writeFileSync(output,JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify({status:report.status,checks:report.checks.length,report:output,...(report.error?{error:report.error}:{})}));}
