/** Real committed research evidence; other app data is isolated UI scaffolding. */
import {test,expect} from '@playwright/test';
test('structural report renders on mobile and exposes real cached evidence without computation',async({page,request},info)=>{
 let posts=0;const errors:string[]=[];page.on('pageerror',e=>errors.push(e.message));
 await page.route('**/api/**',async route=>{
  const r=route.request(),u=new URL(r.url());if(r.method()==='POST')posts++;
  if(u.pathname==='/api/engine')return route.continue();
  return route.fulfill({json:u.pathname==='/api/auth'?{user:null}:{games:[],records:[],sources:[],providers:[],rows:[],journal:[]}});
 });
 await page.goto('/#engine');const section=page.getByRole('region',{name:'Structural reconstruction evidence'});await expect(section).toBeVisible();await expect(section).toContainText('No challenger was promoted');await expect(section).toContainText('grades are withdrawn');
 await page.getByLabel('Validation sport').selectOption('CFB');await section.locator('summary').click();await expect(section.getByRole('table')).toContainText('oof game effect');await expect(section).toContainText('0 games');
 const api=await request.get('/api/engine?view=reconstruction');expect(api.status()).toBe(200);const body=await api.json();expect(body.leagues.CFB.candidates.oof_game_effect.brier).toBeCloseTo(.27069766777777776,12);expect(body.resources.hostedSimulationRequests).toBe(0);
 expect(posts).toBe(0);expect(errors).toEqual([]);expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);
 await section.screenshot({path:`artifacts/parallel-v19/reconstruction-${info.project.name}.png`});
});
