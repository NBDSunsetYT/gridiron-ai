// Local build verification only. Never deploys, queries user data or starts models.
import {spawn} from 'node:child_process';
import {readFile,writeFile,mkdir,cp} from 'node:fs/promises';
import {performance} from 'node:perf_hooks';
import {chromium,devices} from '@playwright/test';
const dist='.next-v24-modelbank',out='artifacts/dynamic-v24/completion-final',screens='docs/research/screenshots';
await mkdir(out,{recursive:true});await mkdir(screens,{recursive:true});
await cp(`${dist}/static`,`${dist}/standalone/${dist}/static`,{recursive:true});
await cp('public',`${dist}/standalone/public`,{recursive:true});
const start=performance.now(),server=spawn(process.execPath,[`${dist}/standalone/server.js`],{env:{...process.env,PORT:'3034',HOSTNAME:'127.0.0.1',GRIDIRON_RESEARCH_V24:'1',GRIDIRON_SERVICE_ROLE:'web',GRIDIRON_ASYNC_SIMULATIONS:'1',GRIDIRON_REQUEST_LIFETIME_WORK:'0'},stdio:['ignore','pipe','pipe']});
let log='',browser;
server.stdout.on('data',v=>{log+=v.toString();});server.stderr.on('data',v=>{log+=v.toString();});
try{
  let ready=false;
  for(let attempt=0;attempt<60;attempt++){
    try{const r=await fetch('http://127.0.0.1:3034/research/v24/models?sport=NFL',{signal:AbortSignal.timeout(2000)});if(r.status===200){ready=true;break;}}catch{}
    await new Promise(resolve=>setTimeout(resolve,250));
  }
  if(!ready)throw Error('Local production-build server did not become ready');
  const startupToHttpMs=performance.now()-start;browser=await chromium.launch({headless:true});const checks=[];
  for(const viewport of ['iphone','desktop']){
    const context=await browser.newContext(viewport==='iphone'?devices['iPhone 13']:{viewport:{width:1440,height:1000}});
    for(const sport of ['NFL','CFB','NBA']){
      const page=await context.newPage(),errors=[],apiCalls=[];page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>{if(new URL(r.url()).pathname.startsWith('/api/'))apiCalls.push(r.url());});
      const began=performance.now(),response=await page.goto(`http://127.0.0.1:3034/research/v24/models?sport=${sport}`,{waitUntil:'networkidle'});
      const rows=await page.locator('tbody tr').count(),horizontalOverflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth);
      const check={viewport,sport,httpStatus:response.status(),rows,horizontalOverflow,errors,apiCalls,wallMs:performance.now()-began};
      if(response.status()!==200||rows!==(sport==='NBA'?21:16)||horizontalOverflow||errors.length||apiCalls.length)throw Error(JSON.stringify(check));
      checks.push(check);if(sport==='NBA')await page.screenshot({path:`${screens}/specialized-v24-${viewport}.png`,fullPage:true});await page.close();
    }
    await context.close();
  }
  const status=await readFile(`/proc/${server.pid}/status`,'utf8'),rssKiB=Number(status.match(/^VmRSS:\s+(\d+)/m)?.[1]);
  const result={scope:'Local production-build Chromium checks, not physical iPhone or deployed Render testing',startupToHttpMs,rssKiB,checks,modelJobsTriggered:0};
  await writeFile(`${out}/browser.json`,JSON.stringify(result,null,2));console.log(JSON.stringify({checks:checks.length,startupToHttpMs,rssKiB,modelJobsTriggered:0}));
}finally{
  await browser?.close();server.kill('SIGTERM');await writeFile(`${out}/browser-server.log`,log);
}
