/** Read-only browser verification against a deployed HTTPS app. Uses an existing
 * disposable QA account; never registers accounts, writes finances, or runs a
 * simulation. Do not enable tracing: credentials must not enter test artifacts. */
import {readFileSync,writeFileSync,mkdirSync,statSync} from 'node:fs';
import assert from 'node:assert/strict';
import {chromium,devices,expect} from '@playwright/test';

const base=new URL(process.env.BASE_URL||'https://gridiron-ai-gray.vercel.app');
assert.equal(base.protocol,'https:','Production PWA verification requires HTTPS.');
const credentialsPath=process.env.QA_CREDENTIALS_FILE||'/tmp/gridiron-production-qa.json';
assert.equal(statSync(credentialsPath).mode&0o077,0,'QA credentials must be private (0600).');
const raw=JSON.parse(readFileSync(credentialsPath,'utf8'));
const account=(Array.isArray(raw)?raw:raw.accounts)?.[0];
assert.ok(account?.id&&/qa/i.test(account.email)&&account.email.endsWith('@example.test'),'Only an existing disposable QA identity is supported.');
const expectedBalance=Number(process.env.QA_EXPECTED_BALANCE_CENTS||52500);
const expectedProfit=Number(process.env.QA_EXPECTED_PL_CENTS||7500);
const profiles=[['desktop-chromium',devices['Desktop Chrome']],['iphone-chromium',devices['iPhone 13']]];
const checks=[];
const check=(profile,name)=>{checks.push({profile,name,status:'passed'});console.log(JSON.stringify({profile,check:name,status:'passed'}));};
const proxyValue=process.env.HTTPS_PROXY||process.env.https_proxy||process.env.HTTP_PROXY||process.env.http_proxy;
const proxy=proxyValue?(()=>{const url=new URL(proxyValue);return{server:url.origin,...url.username?{username:decodeURIComponent(url.username)}:{},...url.password?{password:decodeURIComponent(url.password)}:{}};})():undefined;
let browser;
try{
 browser=await chromium.launch({headless:true,...proxy?{proxy}:{}});
 for(const[name,device]of profiles){
  const{defaultBrowserType:_browser,...deviceOptions}=device;
  const context=await browser.newContext(deviceOptions);
  const page=await context.newPage(),pageErrors=[];
  page.on('pageerror',()=>pageErrors.push('uncaught_browser_exception'));
  await page.goto(base.href,{waitUntil:'networkidle',timeout:90000});
  await expect(page.getByRole('button',{name:'Sign in',exact:true})).toBeVisible();
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'Public layout must fit the viewport.');
  const manifestResponse=await context.request.get(new URL('/manifest.webmanifest',base).href);assert.equal(manifestResponse.status(),200);
  assert.match(manifestResponse.headers()['content-type']||'',/json/);
  const manifest=await manifestResponse.json();assert.equal(manifest.display,'standalone');assert.equal(manifest.start_url,'/');
  for(const[size,path]of [[192,manifest.icons.find(i=>i.sizes==='192x192')?.src],[512,manifest.icons.find(i=>i.sizes==='512x512')?.src],[180,'/apple-touch-icon.png']]){
   assert.ok(path,`A real ${size}px icon must be declared.`);const response=await context.request.get(new URL(path,base).href);assert.equal(response.status(),200);const png=await response.body();assert.equal(png.subarray(0,8).toString('hex'),'89504e470d0a1a0a');assert.equal(png.readUInt32BE(16),size);assert.equal(png.readUInt32BE(20),size);
  }
  const metadata=await page.evaluate(()=>({viewport:document.querySelector('meta[name="viewport"]')?.content,apple:document.querySelector('meta[name="apple-mobile-web-app-capable"]')?.content,touch:document.querySelector('link[rel="apple-touch-icon"]')?.getAttribute('href')}));
  assert.match(metadata.viewport||'',/viewport-fit=cover/);assert.equal(metadata.apple,'yes');assert.ok(metadata.touch);
  const safeAreas=await page.evaluate(()=>Array.from(document.styleSheets).some(sheet=>{try{return Array.from(sheet.cssRules).some(rule=>/safe-area-inset/.test(rule.cssText));}catch{return false;}}));assert.ok(safeAreas,'The loaded app styles must include iPhone safe-area support.');
  if(name==='iphone-chromium')await expect(page.getByRole('navigation',{name:'Mobile navigation'})).toBeVisible();
  check(name,'Public HTTPS app, real PNG icons, standalone metadata, safe areas and responsive navigation');

  await page.getByRole('button',{name:'Sign in',exact:true}).click();
  await page.getByLabel('Email',{exact:true}).fill(account.email);await page.getByLabel('Password',{exact:true}).fill(account.password);
  await page.getByRole('button',{name:'Sign in securely',exact:true}).click();await expect(page.getByRole('dialog')).toHaveCount(0,{timeout:60000});
  await expect(page.getByRole('button',{name:'Account settings',exact:true})).toBeVisible();
  const cookies=await context.cookies(base.origin);
  for(const name of ['gridiron_sb_access','gridiron_sb_refresh']){const value=cookies.find(c=>c.name===name);assert.ok(value?.secure&&value.httpOnly&&value.sameSite==='Lax','Authentication cookies must be Secure, HttpOnly and SameSite=Lax.');}
  const read=async path=>{const result=await page.evaluate(async path=>{const response=await fetch('/api/'+path,{cache:'no-store'});return{status:response.status,cacheControl:response.headers.get('cache-control'),body:await response.json()};},path);assert.equal(result.status,200);assert.match(result.cacheControl||'',/private/);assert.match(result.cacheControl||'',/no-store/);return result.body;};
  assert.equal((await read('auth')).user.id,account.id);
  const ledger=await read('ledger');assert.equal(ledger.summary.cashBalanceCents,expectedBalance);assert.equal(ledger.summary.realizedPlCents,expectedProfit);
  check(name,'Actual Supabase sign-in, secure server cookies and persistent QA ledger readback');

  const formattedBalance=new Intl.NumberFormat('en-US',{style:'currency',currency:'USD'}).format(expectedBalance/100);
  await page.goto(new URL('/#bankroll',base).href,{waitUntil:'networkidle'});await expect(page.locator('main').getByText(formattedBalance,{exact:true}).first()).toBeVisible({timeout:30000});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'Authenticated bankroll layout must fit viewport.');
  const history=await read('simulations');const run=history.jobs.find(job=>job.kind==='simulate'&&job.status==='completed'&&job.result?.simulations===10000);assert.ok(run,'A completed real 10,000-game QA run must already exist.');
  const saved=(await read('simulations?id='+encodeURIComponent(run.id))).job;assert.equal(saved.status,'completed');assert.equal(saved.provenanceVerified,true);assert.equal(saved.result.simulations,10000);assert.equal(saved.result.jointOutcomes.reduce((n,row)=>n+row.count,0),10000);
  await page.goto(new URL('/#simulations',base).href,{waitUntil:'networkidle'});await page.getByRole('button',{name:'Run history',exact:true}).click();
  // Table cell text is concatenated without inserted whitespace in textContent.
  // Locate the exact persisted run by identity, then assert the count cell.
  const row=page.locator('tbody tr').filter({hasText:run.id.slice(0,12)}).filter({hasText:'completed'}).first();await expect(row).toBeVisible({timeout:30000});await expect(row.locator('td').nth(1)).toHaveText('10,000 games');await row.getByRole('button',{name:'Inspect',exact:true}).click();
  await expect(page.locator('.metric-tile').filter({hasText:'HOME WIN'})).toBeVisible({timeout:30000});await expect(page.getByLabel('Simulation distribution',{exact:true})).toBeVisible();assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'Saved simulation charts must fit viewport.');
  check(name,'Fresh browser session reopens exact QA finances and attested 10,000-game distributions');
  const screenshots='test-results/production-pwa';mkdirSync(screenshots,{recursive:true});await page.screenshot({path:`${screenshots}/${name}-saved-simulation.png`,fullPage:true});

  await page.evaluate(async()=>{await navigator.serviceWorker.register('/sw.js');await navigator.serviceWorker.ready;});
  await page.waitForFunction(()=>navigator.serviceWorker.controller!==null,null,{timeout:30000});
  const cached=await page.evaluate(async()=>{const result=[];for(const key of await caches.keys()){if(!key.startsWith('gridiron-'))continue;const cache=await caches.open(key);for(const request of await cache.keys()){const response=await cache.match(request);result.push({path:new URL(request.url).pathname,type:response?.headers.get('content-type')||'',policy:response?.headers.get('cache-control')||''});}}return result;});
  assert.ok(cached.some(row=>row.path==='/offline.html'),'The offline shell must actually be cached.');
  assert.ok(cached.every(row=>!row.path.startsWith('/api/')&&!row.path.startsWith('/signin')&&!row.path.startsWith('/signout')),'Private routes must never enter CacheStorage.');
  assert.ok(cached.every(row=>row.path==='/offline.html'||!/text\/html/i.test(row.type)),'Authenticated HTML must not be cached.');
  assert.ok(cached.every(row=>!/(?:^|,)\s*(?:private|no-store)\b/i.test(row.policy)),'Private/no-store responses must not be cached.');
  await context.setOffline(true);await page.goto(new URL('/production-offline-verification',base).href,{waitUntil:'domcontentloaded'});await expect(page.getByText('Your research will be here when you reconnect.',{exact:true})).toBeVisible();await context.setOffline(false);
  check(name,'Actual offline shell with no private API or authenticated HTML cached');
  assert.equal(pageErrors.length,0,'No uncaught JavaScript errors should occur in the verified workflow.');await context.close();
 }
 const report={status:'passed',checkedAt:new Date().toISOString(),baseUrl:base.origin,checks,accountScope:'Existing disposable SYNTHETIC QA owner only',financialWrites:false,accountsCreated:false,simulationComputedByThisScript:false,credentialsIncluded:false,physicalIphoneInstallationTested:false,browserBoundary:'Desktop Chromium and iPhone13 Chromium emulation; Safari/Home Screen installation requires an actual iPhone.'};
 const target=process.env.QA_REPORT_PATH||'docs/reports/production-browser-pwa.json';mkdirSync(new URL('../',new URL(target,'file://'+process.cwd()+'/')),{recursive:true});writeFileSync(target,JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify({status:'passed',checks:checks.length,report:target,physicalIphoneInstallationTested:false}));
}catch(error){console.error(JSON.stringify({status:'failed',passedChecks:checks.length,error:error instanceof Error?error.message:'Browser verification failed'}));process.exitCode=1;}
finally{await browser?.close();}
