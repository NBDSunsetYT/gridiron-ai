import {expect,test} from '@playwright/test';

test('owned compact fit references drive queued simulations without resending a model artifact',async({page})=>{
 const fitId='10000000-0000-4000-8000-000000000001',runId='20000000-0000-4000-8000-000000000001';
 const fit={model:{version:'SYNTHETIC-BROWSER-FIXTURE',teams:['SYNTH-A','SYNTH-B'],source:'SYNTHETIC browser transport only'},summary:{plays:1000},modelReferenceOnly:true,modelJobId:fitId};
 const generated={modelVersion:'SYNTHETIC-BROWSER-FIXTURE',simulations:10000,home:'SYNTH-A',away:'SYNTH-B',seed:1,homeWinProbability:.5,awayWinProbability:.5,tieProbability:0,monteCarloInterval95:[.49,.51],players:{},uncertainty:{model:'SYNTHETIC browser transport fixture only'}};
 const posts:any[]=[];let polls=0;
 await page.route('**/api/simulations*',async route=>{
  const request=route.request(),id=new URL(request.url()).searchParams.get('id');
  let value:any;
  if(request.method()==='POST'){posts.push(request.postDataJSON());value=posts.length===1?{id:runId,status:'queued',pending:true}:{id:'30000000-0000-4000-8000-000000000001',status:'completed',...generated};}
  else if(id===fitId)value={job:{id:fitId,kind:'fit',status:'completed',provenanceVerified:true,result:fit}};
  else if(id===runId){polls++;value={job:{id:runId,kind:'simulate',status:polls===1?'running':'completed',provenanceVerified:true,result:polls===1?null:generated}};}
  else value={jobs:[{id:fitId,kind:'fit',status:'completed',data:{},createdAt:'2026-01-01T00:00:00Z'}],service:{configured:true,compactTransport:true,maxRequestBytes:3800000}};
  await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(value)});
 });
 await page.goto('/#simulations');await page.getByRole('button',{name:'Run history',exact:true}).click();await page.getByRole('button',{name:'Inspect',exact:true}).click();
 await expect(page.getByRole('button',{name:'Export fit reference',exact:true})).toBeVisible();
 await expect(page.getByText(/not a portable model artifact/)).toBeVisible();
 await page.getByRole('button',{name:'Simulate matchup',exact:true}).click();await page.getByLabel('Away team ID').fill('SYNTH-B');await page.getByLabel('Home team ID').fill('SYNTH-A');await page.getByLabel('Actual event start',{exact:true}).fill('2027-01-01T12:00');
 await page.getByRole('button',{name:'Run evidence-based simulation',exact:true}).click();
 await expect(page.getByRole('status').filter({hasText:/Saved job is/})).toBeVisible();
 await expect(page.getByRole('button',{name:'Run evidence-based simulation',exact:true})).toBeEnabled({timeout:20000});
 expect(posts).toHaveLength(1);expect(posts[0].modelJobId).toBe(fitId);expect(posts[0]).not.toHaveProperty('model');expect(JSON.stringify(posts[0]).length).toBeLessThan(1000);expect(polls).toBeGreaterThanOrEqual(2);
 await expect(page.locator('.metric-tile').filter({hasText:'HOME WIN'})).toBeVisible();
 await page.getByLabel('Load a fitted model or owned fit reference').setInputFiles({name:'synthetic-raw-model.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify({model:{version:'SYNTHETIC-RAW-MODEL',signature:'SYNTHETIC',teams:['SYNTH-A','SYNTH-B']}}))});
 await expect(page.getByText(/Fitted model loaded. Version SYNTHETIC-RAW-MODEL/)).toBeVisible();await page.getByRole('button',{name:'Run evidence-based simulation',exact:true}).click();await expect.poll(()=>posts.length).toBe(2);expect(posts[1]).not.toHaveProperty('modelJobId');expect(posts[1].model.version).toBe('SYNTHETIC-RAW-MODEL');
});
