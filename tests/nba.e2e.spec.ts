import{test,expect}from'@playwright/test';
test('NBA guest navigation and candidate evidence fit desktop and iPhone',async({page})=>{
 const errors:string[]=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto('/#nba');await expect(page.getByRole('heading',{name:'Every possession matters.'})).toBeVisible();
 await expect(page.getByRole('tablist')).toHaveCount(0);
 for(const tab of ['props','simulations','performance','saved','games']){
  await page.evaluate(value=>{window.location.hash='nba/'+value;},tab);await expect(page.locator('main .nba-page')).toBeVisible();
  await page.waitForTimeout(150);expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'NBA '+tab+' horizontal overflow').toBe(true);
 }
 await page.goto('/#engine');await expect(page.getByRole('heading',{name:'Evidence before confidence.'})).toBeVisible();await expect(page.getByText('Strict pregame-qualified games',{exact:true})).toBeVisible();
 expect(errors).toEqual([]);
});
test('NBA private research denies guests and invalid requests cannot start work',async({page})=>{
 await page.goto('/#nba');const status=await page.evaluate(async()=>{const saved=await fetch('/api/nba?view=saved'),invalid=await fetch('/api/nba',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:'analyze',gameId:'cfb:espn:1',simulations:10000})});return [saved.status,invalid.status];});expect(status).toEqual([401,400]);
});
test('live NBA backend completes ten thousand real games and renders distributions',async({page},info)=>{
 test.skip(process.env.E2E_LIVE_NBA!=='1','Requires actual configured worker and persistent Supabase research storage.');test.setTimeout(300000);
 await page.goto('/#nba');await expect(page.getByRole('heading',{name:'Upcoming NBA games'})).toBeVisible();
 const button=page.getByRole('button',{name:'Analyze game',exact:true}).filter({visible:true});await expect(button.first()).toBeVisible({timeout:30000});
 const responsePromise=page.waitForResponse(r=>r.url().includes('/api/nba')&&r.request().method()==='POST',{timeout:260000});await page.getByRole('button',{name:'Analyze game',exact:true}).all().then(async buttons=>{for(const b of buttons){if(await b.isEnabled()){await b.click();return;}}throw Error('No real upcoming NBA matchup available.');});
 const response=await responsePromise;const value=await response.json();expect(response.status(),JSON.stringify(value)).toBe(200);expect(value.analysis.result.simulations).toBe(10000);expect(value.analysis.result.quality.playerTeamPointsReconciled).toBe(true);expect(value.analysis.result.calibratedProbability).toBeNull();
 await expect(page.getByText('Home win · raw estimate',{exact:true})).toBeVisible();await expect(page.locator('.reality-table tbody tr').first()).toBeVisible();expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);
 await page.evaluate(()=>{(document.activeElement as HTMLElement)?.blur();window.scrollTo(0,0);});await page.waitForTimeout(200);
 await page.screenshot({path:'docs/screenshots/v15-nba-'+info.project.name+'.png',fullPage:true});
 const repeat=await page.evaluate(async gameId=>{const r=await fetch('/api/nba',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:'analyze',gameId,simulations:10000})});return{status:r.status,data:await r.json()};},value.analysis.game.id);expect(repeat.status).toBe(200);const reopened=repeat.data;expect(reopened.analysis.id).toBe(value.analysis.id);expect(reopened.analysis.result.players).toEqual(value.analysis.result.players);await page.reload();await expect(page.getByText('Home win · raw estimate',{exact:true})).toBeVisible();await expect(page.locator('.reality-table tbody tr').first()).toBeVisible();
});
test('an archived public NBA analysis reopens after a full browser reload without another simulation',async({page})=>{
 test.setTimeout(120000);
 const id=process.env.E2E_NBA_ANALYSIS_ID;test.skip(!id,'Requires a real public NBA research reference.');
 let simulations=0;page.on('request',r=>{if(r.url().includes('/api/nba')&&r.method()==='POST')simulations++;});
 await page.goto('/#nba/simulations/'+id);await expect(page.getByText('Home win · raw estimate',{exact:true})).toBeVisible({timeout:60000});await expect(page.getByRole('figure',{name:'Simulated outcome distribution'})).toBeVisible();const first=await page.locator('.reality-table tbody').innerText();await page.reload();await expect(page.locator('.reality-table tbody')).toHaveText(first,{timeout:60000,useInnerText:true});await page.getByLabel('Hypothetical threshold',{exact:true}).fill('100000');await expect(page.getByTestId('nba-threshold-probability')).toContainText('0.0% raw probability');await page.getByLabel('NBA outcome direction',{exact:true}).selectOption('under');await expect(page.getByTestId('nba-threshold-probability')).toContainText('100.0% raw probability');expect(simulations).toBe(0);expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);
});
