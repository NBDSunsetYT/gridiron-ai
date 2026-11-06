/** Read-only deployed/staged verification. No account, price or forecast fixtures. */
import {chromium,devices} from '@playwright/test';
import {mkdirSync,writeFileSync} from 'node:fs';
import {EnvHttpProxyAgent,setGlobalDispatcher} from 'undici';
const base=process.env.VERIFY_BASE_URL||'http://127.0.0.1:3026';
const out=process.env.VERIFY_OUTPUT||'artifacts/render-migration-v24';mkdirSync(out,{recursive:true});
const remote=new URL(base).hostname!=='127.0.0.1';
if(remote&&(process.env.HTTPS_PROXY||process.env.HTTP_PROXY))setGlobalDispatcher(new EnvHttpProxyAgent());
const browser=await chromium.launch({headless:true,...(remote&&process.env.HTTPS_PROXY?{proxy:{server:process.env.HTTPS_PROXY}}:{})});
const rows=[];
try{
 for(const [name,options]of [['iphone',devices['iPhone 13']],['desktop',{viewport:{width:1440,height:1000}}]]){
  const context=await browser.newContext(options),page=await context.newPage(),errors=[],calls=[];
  page.on('pageerror',e=>errors.push(e.message));page.on('response',r=>{if(new URL(r.url()).pathname.startsWith('/api/'))calls.push({path:new URL(r.url()).pathname,status:r.status()});});
  const began=Date.now(),response=await page.goto(base,{waitUntil:'networkidle',timeout:90000});
  await page.screenshot({path:out+'/'+(remote?'render':'local')+'-'+name+'.png',fullPage:true});
  const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),manifest=await page.locator('link[rel=manifest]').getAttribute('href');
  const worker=await page.evaluate(async()=>{await navigator.serviceWorker?.ready;return(await navigator.serviceWorker?.getRegistrations())?.map(r=>({scope:new URL(r.scope).pathname,state:r.active?.state}));});
  rows.push({name,base,httpStatus:response?.status(),wallMs:Date.now()-began,errors,horizontalOverflow:overflow,manifest,serviceWorker:worker,calls});
  await page.goto(base+'/#wallet',{waitUntil:'networkidle'});rows.push({name,view:'wallet_guest',signInVisible:await page.getByRole('button',{name:/sign in/i}).count(),errors:[...errors]});await context.close();
 }
}finally{await browser.close();}
for(const path of ['/manifest.webmanifest','/icon-192.png','/icon-512.png','/apple-touch-icon.png','/sw.js','/api/health','/api/cloud/ledger','/auth/error']){
 const t=Date.now();try{const r=await fetch(base+path,{signal:AbortSignal.timeout(30000)});rows.push({path,status:r.status,wallMs:Date.now()-t,contentType:r.headers.get('content-type'),cacheControl:r.headers.get('cache-control'),...(path==='/api/health'?{health:await r.json()}:{})});}catch{rows.push({path,status:'network_timeout_or_outage'});}
}
writeFileSync(out+'/'+(remote?'render':'local')+'-browser.json',JSON.stringify(rows,null,2));console.log(JSON.stringify(rows));
if(rows.some(r=>r.httpStatus!==undefined&&(r.httpStatus!==200||r.horizontalOverflow||r.errors?.length)))process.exitCode=1;
