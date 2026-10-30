import {test,expect,type Page} from '@playwright/test';
import {publicResearchFixture} from './fixtures/public-nfl';

async function publicTransport(page:Page,{cached=false,failSchedule=false}={}){
 const fixture=publicResearchFixture(),posts:unknown[]=[];let polls=0,scheduleFailure=failSchedule;
 await page.route('**/api/nfl**',async route=>{
  const request=route.request(),path=new URL(request.url()).pathname;
  const respond=(body:unknown,status=200)=>route.fulfill({status,contentType:'application/json',body:JSON.stringify(body)});
  if(path==='/api/nfl'){
   if(scheduleFailure)return respond({error:'SYNTHETIC upstream failure'},503);
   return respond({...fixture.dashboard,games:[{...fixture.game,...(cached?{analysis:fixture.analysis}:{})}]});
  }
  if(path.endsWith('/analyze')){posts.push(request.postDataJSON());expect(request.postDataJSON()).toEqual({simulations:10000});return respond({...fixture.detail,status:cached?'ready':'queued',analysis:cached?fixture.analysis:{...fixture.analysis,status:'queued',result:null,summary:null}},cached?200:202);}
  if(path==='/api/nfl/assistant')return respond({summary:fixture.summary,analysisId:fixture.analysis.id,status:'completed'});
  if(path==='/api/nfl/games/'+fixture.game.id){
   if(cached)return respond(fixture.detail);
   if(!posts.length)return respond({...fixture.detail,analysis:null,status:'ready',summary:null});
   polls++;return respond(polls<2?{...fixture.detail,status:'running',analysis:{...fixture.analysis,status:'running',result:null,summary:null},summary:null}:fixture.detail);
  }
  return respond({error:'SYNTHETIC unsupported test request'},404);
 });
 return{fixture,posts,allowSchedule:()=>{scheduleFailure=false;}};
}

test('a guest taps a game and automatically receives distributions and a truthful sourced explanation',async({page})=>{
 const{fixture,posts}=await publicTransport(page);
 const errors:string[]=[];page.on('pageerror',error=>errors.push(error.message));
 await page.goto('/');await expect(page.getByTestId('game-card-'+fixture.game.id).first()).toBeVisible();
 await page.screenshot({path:`test-results/v5-${test.info().project.name}-guest-home.png`,fullPage:true});
 await expect(page.getByRole('dialog')).toHaveCount(0);await expect(page.locator('main')).not.toContainText(/Supabase|API key|Upload.*CSV/i);await expect(page.locator('main input[type=file]')).toHaveCount(0);
 await page.getByTestId('game-card-'+fixture.game.id).first().click();
 await expect(page.getByRole('heading',{name:'SYN-A at SYN-H',exact:true})).toBeVisible();
 await expect(page.getByRole('status').filter({hasText:'Analyzing this game…'})).toBeVisible();
 await expect(page.getByRole('heading',{name:'How the game could unfold'})).toBeVisible({timeout:25000});expect(posts).toHaveLength(1);
 await page.screenshot({path:`test-results/v5-${test.info().project.name}-guest-game.png`,fullPage:true});
 await page.getByLabel('Game outcome distribution').selectOption('player');await expect(page.getByLabel('Player outcome')).toHaveValue('SYNTHETIC-PLAYER');await expect(page.getByRole('figure',{name:'Simulated outcome distribution'})).toBeVisible();
 await expect(page.locator('main')).toContainText('Verified live prices unavailable');
 await page.getByLabel('Ask about this game').fill('Explain the available injury evidence.');await page.getByRole('button',{name:'Ask GRIDIRON AI',exact:true}).click();
 await expect(page.locator('.public-answer')).toContainText(fixture.summary.text);await expect(page.locator('.public-answer')).toContainText('SOURCED EXPLANATION');
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);expect(errors).toEqual([]);
});

test('fresh shared research opens immediately while Wallet requires only GRIDIRON AI sign-in',async({page})=>{
 const{fixture,posts}=await publicTransport(page,{cached:true});await page.goto('/#games');await page.getByTestId('game-card-'+fixture.game.id).first().click();
 await expect(page.getByRole('heading',{name:'How the game could unfold'})).toBeVisible();expect(posts).toHaveLength(0);
 await expect(page.getByRole('dialog')).toHaveCount(0);await page.goto('/#bankroll');
 await page.getByRole('button',{name:'Continue with GRIDIRON AI',exact:true}).click();await expect(page.getByRole('dialog')).toBeVisible();await expect(page.getByLabel('Email',{exact:true})).toBeVisible();await expect(page.getByLabel('Password',{exact:true})).toBeVisible();
 expect(new URL(page.url()).pathname).toBe('/');await expect(page.getByRole('dialog')).not.toContainText(/Supabase|developer dashboard|service.role|API key/i);
 for(const path of ['/api/ledger','/api/conversations','/api/contracts','/api/records'])expect((await page.request.get(path)).status(),path).toBe(401);
});

test('a feed failure stays an honest retry state and never turns into fake games or a login requirement',async({page})=>{
 const transport=await publicTransport(page,{failSchedule:true});await page.goto('/');await expect(page.getByRole('alert').filter({hasText:'We couldn’t refresh the schedule'})).toBeVisible();await expect(page.locator('[data-testid^="game-card-"]')).toHaveCount(0);await expect(page.getByRole('dialog')).toHaveCount(0);
 transport.allowSchedule();await page.getByRole('button',{name:'Try again',exact:true}).click();await expect(page.getByTestId('game-card-'+transport.fixture.game.id).first()).toBeVisible();
});

test('private conversation history stays in the consumer app and displays saved text without executing HTML',async({page})=>{
 await publicTransport(page,{cached:true});
 const id='30000000-0000-4000-8000-000000000005',title='SYNTHETIC saved game research',literal='<script>window.__gridironInjected=true</script> SYNTHETIC saved explanation';
 await page.route('**/api/auth',route=>route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({user:{id:'10000000-0000-4000-8000-000000000005',email:'SYNTHETIC-browser@example.test'}})}));
 await page.route('**/api/conversations*',route=>route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({conversations:[{id,title,messageCount:2,updatedAt:new Date().toISOString()}]})}));
 await page.route('**/api/conversations/'+id,route=>route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({conversation:{id,title,messages:[{id:'SYNTHETIC-QUESTION',role:'user',content:'SYNTHETIC saved question'},{id:'SYNTHETIC-ANSWER',role:'assistant',content:literal}]}})}));
 await page.goto('/#conversations');await expect(page.getByRole('heading',{name:'Conversations worth keeping.',exact:true})).toBeVisible();await page.getByRole('button',{name:new RegExp(title)}).click();
 const thread=page.getByRole('region',{name:'Saved conversation'});await expect(thread).toContainText('SYNTHETIC saved question');await expect(thread).toContainText(literal);expect(await page.evaluate(()=>(window as Window&{__gridironInjected?:boolean}).__gridironInjected)).toBeUndefined();
 await expect(page.locator('.terminal')).not.toHaveClass(/advanced-mode/);await expect(page.locator('main')).not.toContainText(/Supabase|API key|service.role/i);expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);
});
