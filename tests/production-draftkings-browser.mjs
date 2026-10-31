// Actual remote browser verification. No page.route, market fixtures, logins,
// provider credentials, financial writes or simulated successful feeds.
import assert from 'node:assert/strict';
import {chromium,webkit,devices,expect} from '@playwright/test';
import {mkdir,writeFile} from 'node:fs/promises';
import {dirname} from 'node:path';
const base=new URL(process.env.BASE_URL||'https://gridiron-ai-gray.vercel.app');
assert.equal(base.protocol,'https:');
const report={startedAt:new Date().toISOString(),baseUrl:base.origin,status:'running',mockedResponses:false,privateRecordsChanged:false,liveDraftKingsFeedVerified:false,physicalIphoneInstallationTested:false,checks:[]};
const profiles=[['desktop-chromium',chromium,{viewport:{width:1440,height:1000}}],['iphone-chromium',chromium,{...devices['iPhone 13']}],['iphone-webkit',webkit,{...devices['iPhone 13']}]];
let browser;
async function check(profile,name,work){await work();report.checks.push({profile,name,status:'passed'});console.log(JSON.stringify({profile,name,status:'passed'}));}
try{
 for(const[profile,type,device]of profiles){
  const{defaultBrowserType,...contextOptions}=device;
  browser=await type.launch({headless:true});const context=await browser.newContext(contextOptions),page=await context.newPage();page.setDefaultTimeout(45000);
  await check(profile,'Guest Home shows real NFL games and the actual disconnected-feed diagnosis',async()=>{
   await page.goto(base.origin,{waitUntil:'domcontentloaded',timeout:90000});const response=await context.request.get(new URL('/api/health',base).href);assert.equal(response.status(),200);assert.equal((await response.json()).version,'7.0.1');
   const source=page.getByRole('region',{name:'DraftKings Predictions source availability',exact:true});await expect(source.getByRole('heading',{name:'DraftKings feed not connected',exact:true})).toBeVisible();await expect(source).toContainText('NFL contract listings have not been checked');await expect(source.locator('.market-availability-time')).not.toContainText('Time unavailable');await expect(page.locator('[data-testid^="game-card-"]').first()).toBeVisible();await expect(page.getByRole('dialog')).toHaveCount(0);
  });
  await check(profile,'One Home tap opens the diagnosed NFL contract view without displaying fabricated markets',async()=>{
   await page.getByRole('button',{name:'ANALYZE ALL NFL MARKETS',exact:true}).click();await expect(page.getByRole('heading',{name:'Every market. The exact contract.',exact:true})).toBeVisible();
   const source=page.getByRole('region',{name:'DraftKings Predictions source availability',exact:true});await expect(source.getByRole('heading',{name:'DraftKings feed not connected',exact:true})).toBeVisible();await expect(source).toContainText('App operator action required');await expect(page.getByRole('button',{name:'ANALYZE ALL NFL MARKETS',exact:true})).toBeDisabled();await expect(page.locator('[data-testid^="prop-research-"]')).toHaveCount(0);await expect(page.getByRole('link',{name:'Open DraftKings Predictions NFL'})).toHaveAttribute('href','https://predictions.draftkings.com/en/markets/football/nfl');
  });
  await check(profile,'Verification details distinguish app configuration from an observed source HTTP failure',async()=>{
   const source=page.getByRole('region',{name:'DraftKings Predictions source availability',exact:true});await source.getByText('Verification details',{exact:true}).click();await expect(source).toContainText('App connection');await expect(source).not.toContainText('HTTP 401');await expect(source).not.toContainText('HTTP 429');await expect(source.getByRole('button',{name:'Retry source check',exact:true})).toHaveCount(0);assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));await mkdir('artifacts',{recursive:true});await page.screenshot({path:`artifacts/draftkings-${profile}.png`,fullPage:false});
  });
  await check(profile,'Optional manual capture remains behind GRIDIRON identity and never opens a Supabase dashboard',async()=>{
   const source=page.getByRole('region',{name:'DraftKings Predictions source availability',exact:true});await source.getByRole('button',{name:'Optional verified manual entry',exact:true}).click();await expect(page.getByRole('dialog')).toContainText('YOUR GRIDIRON AI ACCOUNT');assert.equal(new URL(page.url()).origin,base.origin);await page.keyboard.press('Escape');await expect(page.getByRole('dialog')).toHaveCount(0);
  });
  await check(profile,'The preserved Props screen shows the same precise diagnosis on mobile',async()=>{
   await page.goto(new URL('/#props',base).href,{waitUntil:'domcontentloaded',timeout:90000});const source=page.getByRole('region',{name:'DraftKings Predictions source availability',exact:true});await expect(source.getByRole('heading',{name:'DraftKings feed not connected',exact:true})).toBeVisible();await expect(page.getByRole('button',{name:'ANALYZE ALL PLAYER PROPS',exact:true})).toBeDisabled();assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
  });
  await context.close();await browser.close();browser=null;
 }
 report.status='passed';
}catch(error){report.status='failed';report.error=error instanceof Error?error.message:String(error);process.exitCode=1;}
finally{await browser?.close();report.finishedAt=new Date().toISOString();const path=process.env.QA_REPORT_PATH||'docs/reports/draftkings-production-browser.json';await mkdir(dirname(path),{recursive:true});await writeFile(path,JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify({status:report.status,checks:report.checks.length,report:path}));}
