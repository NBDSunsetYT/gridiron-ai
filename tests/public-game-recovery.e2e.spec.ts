/** SYNTHETIC transport fixtures only; never imported by production code. */
import {expect,test,type Page} from '@playwright/test';
import {publicResearchFixture} from './fixtures/public-nfl';

async function recoveryTransport(page:Page,{unverified=false}={}){
 const fixture=publicResearchFixture();let recovered=!unverified,reads=0;const posts:unknown[]=[];
 await page.route('**/api/auth',route=>route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({user:null})}));
 await page.route('**/api/nfl**',route=>{
  const request=route.request(),path=new URL(request.url()).pathname;
  const reply=(body:unknown,status=200)=>route.fulfill({status,contentType:'application/json',body:JSON.stringify(body)});
  const stale={...fixture.detail,status:'queued',inputsVerified:recovered,requiredInputHash:recovered?'SYNTHETIC-VERIFIED-NEW-HASH':null,currentInputHash:recovered?'SYNTHETIC-VERIFIED-NEW-HASH':null,summary:null,analysis:{...fixture.analysis,status:'queued',stale:true,result:null,summary:null,inputHash:'SYNTHETIC-STORED-OUTDATED-HASH',inputsVerified:recovered,requiredInputHash:recovered?'SYNTHETIC-VERIFIED-NEW-HASH':null,currentInputHash:recovered?'SYNTHETIC-VERIFIED-NEW-HASH':null}};
  const current={...fixture.detail,inputsVerified:true,requiredInputHash:'SYNTHETIC-VERIFIED-NEW-HASH',currentInputHash:'SYNTHETIC-VERIFIED-NEW-HASH',analysis:{...fixture.analysis,inputsVerified:true,inputHash:'SYNTHETIC-VERIFIED-NEW-HASH',requiredInputHash:'SYNTHETIC-VERIFIED-NEW-HASH'}};
  if(path==='/api/nfl')return reply(fixture.dashboard);
  if(path.endsWith('/analyze')){posts.push(request.postDataJSON());return reply(unverified?current:stale,unverified?200:202);}
  if(path==='/api/nfl/games/'+fixture.game.id){reads++;return reply(unverified&&recovered&&posts.length?current:stale);}
  return reply({error:'SYNTHETIC unsupported request'},404);
 });
 return{fixture,posts,reads:()=>reads,recover:()=>{recovered=true;}};
}

test('a stale queued game cannot block one automatic request for a verified required input hash',async({page})=>{
 const transport=await recoveryTransport(page);await page.goto('/#games/'+transport.fixture.game.id);
 await expect.poll(()=>transport.posts.length,{timeout:12000}).toBe(1);expect(transport.posts[0]).toEqual({simulations:10000});
 await expect.poll(()=>transport.reads(),{timeout:20000}).toBeGreaterThanOrEqual(3);expect(transport.posts).toHaveLength(1);
 await expect(page.getByRole('dialog')).toHaveCount(0);
});

test('unverified inputs enqueue nothing and a verified new hash recovers the automatic game flow once',async({page})=>{
 const transport=await recoveryTransport(page,{unverified:true});await page.goto('/#games/'+transport.fixture.game.id);
 await expect.poll(()=>transport.reads(),{timeout:12000}).toBeGreaterThanOrEqual(2);expect(transport.posts).toHaveLength(0);
 transport.recover();await expect.poll(()=>transport.posts.length,{timeout:12000}).toBe(1);await expect(page.getByRole('heading',{name:'How the game could unfold',exact:true})).toBeVisible();expect(transport.posts[0]).toEqual({simulations:10000});
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);
});
