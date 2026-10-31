import {test,expect,type Page} from '@playwright/test';
import {playerPropFixture} from './fixtures/player-props';

test.beforeEach(async({page})=>{await page.addInitScript(()=>sessionStorage.setItem('gridiron-market-provider-v7','Kalshi'));const fixture=playerPropFixture();await page.route('**/api/nfl**',route=>route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(fixture.nfl.dashboard)}));});

async function transport(page:Page,{initiallyUnavailable=false,tamperDefinition=false}={}){
 const fixture=playerPropFixture(),posts:unknown[]=[],queries:URLSearchParams[]=[];let scanned=false,unavailable=initiallyUnavailable;
 if(tamperDefinition){fixture.receiverYes.currentContract={...fixture.receiverYes.currentContract!,threshold:99.5,yesAskCents:'88'};fixture.scan.results[0]=fixture.receiverYes;}
 await page.route('**/api/auth',route=>route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({user:null})}));
 await page.route('**/api/nfl**',route=>route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(fixture.nfl.dashboard)}));
 await page.route('**/api/props**',async route=>{
  const request=route.request(),url=new URL(request.url()),path=url.pathname;
  const reply=(body:unknown,status=200)=>route.fulfill({status,contentType:'application/json',body:JSON.stringify(body)});
  if(path==='/api/props/analyze'){scanned=true;posts.push(request.postDataJSON());return reply({...fixture.scan,status:'queued',results:[],progress:{completed:0,total:4,phase:'checking verified sources',gamesComplete:0,gamesTotal:1}},202);}
  if((path==='/api/props/combinations'||path==='/api/props/what-if')&&request.method()==='GET')return reply({jobs:[],private:true});
  if(path==='/api/props/assistant')return reply({summary:{text:'SYNTHETIC sourced explanation; unknown fees prevent an unconditional value claim.',generatedByAI:false,citations:fixture.scan.sources}});
  if(path.startsWith('/api/props/results/')){const result=fixture.results.find(row=>row.id===path.split('/').at(-1));return result?reply({research:result}):reply({error:'SYNTHETIC research not found'},404);}
  if(path==='/api/props'){
   queries.push(url.searchParams);if(unavailable)return reply({error:'SYNTHETIC source temporarily unavailable'},503);
   if(url.searchParams.get('category')==='passingYards')return reply({...fixture.scan,results:url.searchParams.get('side')==='NO'?[fixture.passingNo]:[fixture.passingYes,fixture.passingNo],totalResults:url.searchParams.get('side')==='NO'?1:2,nextCursor:null});
   if(url.searchParams.get('side')==='NO')return reply({...fixture.scan,results:[fixture.receiverNo,fixture.passingNo],totalResults:2,nextCursor:null});
   if(url.searchParams.get('cursor')==='2')return reply({...fixture.scan,results:[fixture.passingYes,fixture.passingNo],nextCursor:null});
   return reply(scanned?fixture.scan:{...fixture.scan,runId:null,results:[],status:'unavailable',totalResults:0,nextCursor:null});
  }
  return reply({error:'SYNTHETIC unsupported transport request'},404);
 });
 return{fixture,posts,queries,allow:()=>{unavailable=false;scanned=true;}};
}

test('one home tap starts the verified prop scan once and clearly separates raw probability, calibration and costs',async({page})=>{
 const t=await transport(page),errors:string[]=[];page.on('pageerror',error=>errors.push(error.message));await page.goto('/');await page.screenshot({path:`test-results/v6-${test.info().project.name}-home.png`,fullPage:false});
 await page.getByRole('button',{name:'ANALYZE PLAYER PROPS',exact:true}).click();await expect(page.getByRole('heading',{name:'Every threshold has a story.'})).toBeVisible();
 await expect(page.getByRole('status')).toContainText('Checking verified sources');await expect(page.getByRole('status')).toContainText('0 of 4 outcomes checked.');await expect(page.getByTestId('prop-research-'+t.fixture.receiverYes.id)).toBeVisible({timeout:20000});
 expect(t.posts).toEqual([{}]);const card=page.getByTestId('prop-research-'+t.fixture.receiverYes.id);
 await expect(card).toContainText('SYNTHETIC Receiver');await expect(card).toContainText('Conditional simulation estimate');await expect(card.locator('.prop-calibrated')).toContainText('Unavailable');await expect(card.locator('.prop-calibrated')).not.toContainText('70.0%');
 await expect(card).toContainText('Fees are not verified');await expect(card.locator('.prop-price-grid')).toContainText('68¢');await expect(card.locator('.prop-card-source')).toContainText('Kalshi');await expect(card).not.toContainText('DraftKings live quote');
 await expect(card.getByRole('figure',{name:'Simulated outcome distribution'})).toBeVisible();await card.getByText('Quoted prices and captured snapshot',{exact:true}).click();await expect(card.locator('dd')).toContainText(['55¢']);
 await page.reload();await expect(page.getByTestId('prop-research-'+t.fixture.receiverYes.id)).toBeVisible();expect(t.posts).toHaveLength(1);
 await expect(page.getByRole('dialog')).toHaveCount(0);await expect(page.locator('main')).not.toContainText(/Supabase|service.role|API key/i);expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);expect(errors).toEqual([]);
 await page.screenshot({path:`test-results/v6-${test.info().project.name}-props.png`,fullPage:true});await page.evaluate(()=>window.scrollTo(0,0));await page.screenshot({path:`test-results/v6-${test.info().project.name}-props-viewport.png`,fullPage:false});
});

test('category filtering queries all stored research before pagination and more outcomes remain accessible',async({page})=>{
 const t=await transport(page);t.allow();await page.goto('/#props');await expect(page.getByTestId('prop-research-'+t.fixture.receiverYes.id)).toBeVisible();
 await page.getByRole('button',{name:'Show more researched outcomes'}).click();await expect(page.getByTestId('prop-research-'+t.fixture.passingYes.id)).toBeVisible();expect(t.queries.some(query=>query.get('cursor')==='2')).toBe(true);
 await page.getByLabel('Player prop category').selectOption('passing_yards');await expect(page.getByTestId('prop-research-'+t.fixture.receiverYes.id)).toHaveCount(0);await expect(page.getByTestId('prop-research-'+t.fixture.passingYes.id)).toBeVisible();expect(t.queries.some(query=>query.get('category')==='passingYards')).toBe(true);
 await page.getByLabel('Contract outcome').selectOption('no');await expect.poll(()=>t.queries.at(-1)?.get('side')).toBe('NO');await expect(page.getByTestId('prop-research-'+t.fixture.passingYes.id)).toHaveCount(0);await expect(page.getByTestId('prop-research-'+t.fixture.passingNo.id)).toBeVisible();
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);
});

test('a changed contract definition cannot be compared with the probability captured for a different threshold',async({page})=>{
 const t=await transport(page,{tamperDefinition:true});t.allow();await page.goto('/#props');const card=page.getByTestId('prop-research-'+t.fixture.receiverYes.id);await expect(card).toBeVisible();
 await expect(card).toContainText('latest contract definition differs');await expect(card).toContainText('Historical simulation estimate');await expect(card.locator('.prop-price-grid')).not.toContainText('88¢');await expect(card.locator('.prop-price-grid')).toContainText('Unavailable');
});

test('failed prop sources remain a retry state without fabricated outcomes or a developer login',async({page})=>{
 const t=await transport(page,{initiallyUnavailable:true});await page.goto('/#props');await expect(page.getByRole('alert').filter({hasText:'SYNTHETIC source temporarily unavailable'})).toContainText('SYNTHETIC source temporarily unavailable');await expect(page.locator('[data-testid^="prop-research-"]')).toHaveCount(0);await expect(page.getByRole('dialog')).toHaveCount(0);
 t.allow();await page.getByRole('button',{name:'Retry',exact:true}).click();await expect(page.getByTestId('prop-research-'+t.fixture.receiverYes.id)).toBeVisible();await expect(page.locator('main input[type=file]')).toHaveCount(0);
});

test('guest outcome combinations request an app identity without placing a wager',async({page})=>{
 const t=await transport(page);t.allow();let financialWrites=0;await page.route('**/api/bets',route=>{financialWrites++;return route.fulfill({status:500,body:'SYNTHETIC unexpected wager write'});});
 await page.goto('/#props');await page.getByTestId('prop-research-'+t.fixture.receiverYes.id).getByRole('checkbox',{name:'Compare together'}).check();await page.getByTestId('prop-research-'+t.fixture.receiverNo.id).getByRole('checkbox',{name:'Compare together'}).check();
 await page.getByRole('button',{name:'Analyze selected outcomes'}).click();await expect(page.getByRole('dialog')).toBeVisible();await expect(page.getByRole('dialog')).toContainText('YOUR GRIDIRON AI ACCOUNT');expect(financialWrites).toBe(0);
});

test('the Wallet records actual contract price, inclusive stake and settlement time without synthesizing sportsbook odds',async({page})=>{
 const placed:Record<string,unknown>[]=[],settled:Record<string,unknown>[]=[],bets:Record<string,unknown>[]=[];const pendingRefresh:{release?:(()=>void)}={};let delayedRefresh=false;
 await page.route('**/api/auth',route=>route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({user:{id:'SYNTHETIC-WALLET-OWNER',email:'synthetic-wallet@example.test'}})}));
 await page.route('**/api/ledger',async route=>{if(bets.some(bet=>bet.result==='pending')&&!delayedRefresh){delayedRefresh=true;await new Promise<void>(resolve=>{pendingRefresh.release=resolve;});}return route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({accounts:[],transactions:[],chart:[],summary:{cashBalanceCents:100000,realizedPlCents:0},bets})});});
 await page.route('**/api/bets',route=>{const body=route.request().postDataJSON();if(body.action==='place'){placed.push(body);bets.push({...body,id:'SYNTHETIC-CONTRACT-WAGER',status:'pending',result:'pending',stakeCents:4200,odds:null});}else{settled.push(body);bets[0]={...bets[0],status:'won',result:'won',payoutCents:5000};}return route.fulfill({status:201,contentType:'application/json',body:JSON.stringify({id:'SYNTHETIC-CONTRACT-WAGER'})});});
 await page.goto('/#bankroll');await page.getByRole('button',{name:'Record wager',exact:true}).click();await expect(page.getByLabel('Record type')).toHaveValue('event_contract');await expect(page.getByLabel('American odds',{exact:true})).toHaveCount(0);
 await page.getByLabel('Event',{exact:true}).fill('SYNTHETIC actual-fill interface test');await page.getByLabel('Player (optional)').fill('SYNTHETIC Receiver');await page.getByLabel('Market',{exact:true}).fill('SYNTHETIC receiving yards contract');await page.getByLabel('Selection',{exact:true}).fill('SYNTHETIC YES');
 await page.getByLabel('Contract price (cents)').fill('40');await page.getByLabel('Amount spent including fees (USD)').fill('42.00');await page.getByLabel('Contract quantity (optional)').fill('100');await page.getByLabel('Total entry fees (cents)',{exact:true}).fill('200');await page.getByLabel('Date & time',{exact:true}).fill('2026-10-29T12:00');await page.getByRole('dialog').evaluate(node=>{node.scrollTop=0;});await page.screenshot({path:`test-results/v6-${test.info().project.name}-wallet-contract.png`,fullPage:false});await page.getByRole('button',{name:'Save record',exact:true}).click();
 await expect(page.getByRole('dialog')).toHaveCount(0);expect(placed).toHaveLength(1);expect(placed[0]).toMatchObject({marketInstrument:'event_contract',player:'SYNTHETIC Receiver',contractPriceCents:'40',contractQuantity:100,entryFeeCents:'200',stake:'42.00'});expect(placed[0]).not.toHaveProperty('odds');
 await expect.poll(()=>Boolean(pendingRefresh.release)).toBe(true);await expect(page.getByRole('button',{name:'Step 2: Enter result'})).toBeDisabled();pendingRefresh.release!();await page.getByRole('button',{name:'Step 2: Enter result'}).click();await page.getByLabel('Total payout including returned stake (USD)').fill('50.00');await page.getByLabel('Settlement date & time').fill('2026-10-30T12:00');await page.getByRole('button',{name:'Confirm settlement'}).click();
 await expect(page.getByRole('dialog')).toHaveCount(0);expect(settled).toHaveLength(1);expect(settled[0]).toMatchObject({action:'settle',id:'SYNTHETIC-CONTRACT-WAGER',result:'won',payout:'50.00'});expect(Number.isFinite(Date.parse(String(settled[0].settlementTime)))).toBe(true);expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);
});

test('a signed-in hypothetical combination displays shared-game probability separately from the independence comparison',async({page})=>{
 const t=await transport(page);t.allow();await page.route('**/api/auth',route=>route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({user:{id:'SYNTHETIC-COMBINATION-OWNER',email:'synthetic-combination@example.test'}})}));
 let submitted:unknown,privatePosts=0;
 await page.route('**/api/props/combinations**',route=>{if(route.request().method()==='POST'){submitted=route.request().postDataJSON();privatePosts++;return route.fulfill({status:202,contentType:'application/json',body:JSON.stringify({id:'60000000-0000-4000-8000-000000000099',kind:'combination',status:'queued'})});}if(new URL(route.request().url()).pathname==='/api/props/combinations')return route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({jobs:submitted?[{id:'60000000-0000-4000-8000-000000000099',kind:'combination',status:'completed',game:t.fixture.nfl.game,updatedAt:new Date().toISOString()}]:[],private:true})});return route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({id:'60000000-0000-4000-8000-000000000099',kind:'combination',status:'completed',result:{conditional:true,combination:{jointProbability:.6,independenceAssumptionProbability:.49,simulations:10000,monteCarloInterval95:[.5904,.6096],parameterInterval95:null,limitations:['SYNTHETIC aligned outcomes only; no execution offer.']},valuation:{netExpectedValueCents:null,reason:'SYNTHETIC no verified combined offer or fees.'}}})});});
 await page.goto('/#props');await page.getByRole('button',{name:'Show more researched outcomes'}).click();await page.getByTestId('prop-research-'+t.fixture.receiverYes.id).getByRole('checkbox',{name:'Compare together'}).check();await page.getByTestId('prop-research-'+t.fixture.passingYes.id).getByRole('checkbox',{name:'Compare together'}).check();await page.getByRole('button',{name:'Analyze selected outcomes'}).click();
 await expect(page.locator('.props-combination-result')).toContainText('60.0%',{timeout:15000});await expect(page.locator('.props-combination-result')).toContainText('49.0%');await expect(page.locator('.props-combination-result')).toContainText('No actual wager is recorded');expect(submitted).toEqual({researchIds:[t.fixture.receiverYes.id,t.fixture.passingYes.id]});await page.locator('.props-saved-list').getByRole('button',{name:/Hypothetical combination/}).click();await expect(page.getByRole('region',{name:'Saved private prop research'})).toContainText('60.0%');await page.reload();await expect(page.getByRole('region',{name:'Saved private prop research'})).toContainText('60.0%');expect(privatePosts).toBe(1);
});

test('a supported availability what-if remains hypothetical and does not overwrite the current research snapshot',async({page})=>{
 const t=await transport(page);t.allow();await page.route('**/api/auth',route=>route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({user:{id:'SYNTHETIC-SCENARIO-OWNER',email:'synthetic-scenario@example.test'}})}));
 let submitted:unknown;
 await page.route('**/api/props/what-if**',route=>{if(route.request().method()==='POST'){submitted=route.request().postDataJSON();return route.fulfill({status:202,contentType:'application/json',body:JSON.stringify({id:'SYNTHETIC-PRIVATE-SCENARIO',status:'queued'})});}return route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({id:'SYNTHETIC-PRIVATE-SCENARIO',kind:'what_if',status:'completed',result:{hypothetical:true,currentVerifiedConditionsChanged:false,delta:{homeWinProbability:-.05,contracts:[{researchId:t.fixture.receiverYes.id,baselineProbability:.7,modifiedProbability:.6,delta:-.1}]},limitations:['SYNTHETIC historical cohort comparison only; no causal effect claimed.']}})});});
 await page.goto('/#props');const card=page.getByTestId('prop-research-'+t.fixture.receiverYes.id);await card.getByText('Optional availability what-if',{exact:true}).click();await card.getByLabel('Assumed player availability').selectOption('limited');await card.getByRole('button',{name:'Compare hypothetical availability'}).click();
 await expect(card.locator('.prop-scenario-result')).toContainText('60.0%',{timeout:15000});await expect(card.locator('.prop-scenario-result')).toContainText('-10.00 percentage points');await expect(card.locator('.prop-probability-row')).toContainText('70.0%');expect(submitted).toEqual({gameId:t.fixture.receiverYes.contract.gameId,playerId:t.fixture.receiverYes.contract.playerId,status:'limited',researchIds:[t.fixture.receiverYes.id]});
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);
});


test('private account summaries are visibly sourced reports and can be reopened from conversation history',async({page})=>{
 const id='60000000-0000-4000-8000-000000000098',answer='SYNTHETIC account report: recorded withdrawals are $150.00. This is a database calculation, not an OpenAI answer.';let saved=false;
 await page.route('**/api/auth',route=>route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({user:{id:'SYNTHETIC-CHAT-OWNER',email:'synthetic-chat@example.test'}})}));
 await page.route('**/api/conversations**',route=>{const path=new URL(route.request().url()).pathname;if(route.request().method()==='POST'){saved=true;return route.fulfill({status:201,contentType:'application/json',body:JSON.stringify({conversation:{id}})});}return route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(path==='/api/conversations'?{conversations:saved?[{id,title:'SYNTHETIC recorded withdrawals',updatedAt:new Date().toISOString()}]:[]}:{conversation:{id,messages:[{role:'user',content:'Show my recorded withdrawals this month.'},{role:'assistant',content:answer,data:{generatedByAI:false,method:'recorded_account_report',citations:[{name:'SYNTHETIC own ledger'}]}}]}})});});
 await page.route('**/api/assistant',route=>route.fulfill({status:200,contentType:'text/event-stream',body:'data: '+JSON.stringify({conversationId:id,generatedByAI:false,method:'recorded_account_report'})+'\n\ndata: '+JSON.stringify({text:answer})+'\n\ndata: '+JSON.stringify({citations:[{name:'SYNTHETIC own ledger'}],generatedByAI:false})+'\n\ndata: [DONE]\n\n'}));
 await page.goto('/#private-ai');await page.getByLabel('Ask GRIDIRON Intelligence').fill('Show my recorded withdrawals this month.');await page.getByRole('button',{name:'Send message',exact:true}).click();await expect(page.locator('.chat-message.assistant')).toContainText(answer);await expect(page.locator('.chat-message.assistant .message-label')).toHaveText('SOURCED RECORD REPORT');await expect(page.locator('main')).not.toContainText('Server-side OpenAI');await page.reload();await page.getByRole('button',{name:/^SYNTHETIC recorded withdrawals/}).click();await expect(page.locator('.chat-message.assistant .message-label')).toHaveText('SOURCED RECORD REPORT');expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);
});


test('an outdated pagination result cannot mix a different cached result set into the current research list',async({page})=>{
 const t=await transport(page);t.allow();
 await page.route(/\/api\/props(?:\?.*)?$/,route=>{const url=new URL(route.request().url()),later=Boolean(url.searchParams.get('cursor'));return route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({...t.fixture.scan,runId:'SYNTHETIC-SAME-HEADER',resultSetId:later?'SYNTHETIC-DIFFERENT-PHYSICAL-SET':'SYNTHETIC-INITIAL-PHYSICAL-SET',results:later?[t.fixture.passingYes]:[t.fixture.receiverYes,t.fixture.receiverNo],totalResults:4,nextCursor:'2'})});});
 await page.goto('/#props');await expect(page.getByTestId('prop-research-'+t.fixture.receiverYes.id)).toBeVisible();await page.getByRole('button',{name:'Show more researched outcomes'}).click();await expect(page.getByRole('button',{name:'Show more researched outcomes'})).toBeEnabled();await expect(page.getByTestId('prop-research-'+t.fixture.passingYes.id)).toHaveCount(0);await expect(page.getByTestId('prop-research-'+t.fixture.receiverYes.id)).toBeVisible();
});


test('a failed HTTP200 scan visibly explains the pause while retaining saved research and offering a real retry',async({page})=>{
 const t=await transport(page);t.allow();const message='SYNTHETIC source verification interrupted; saved predictions retained.';
 await page.route(/\/api\/props(?:\?.*)?$/,route=>route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({...t.fixture.scan,status:'failed',message})}));
 await page.goto('/#props');await expect(page.getByRole('alert').filter({hasText:message})).toBeVisible();await expect(page.getByTestId('prop-research-'+t.fixture.receiverYes.id)).toBeVisible();await expect(page.locator('.props-progress')).toHaveCount(0);await page.getByRole('button',{name:'Retry research',exact:true}).click();await expect.poll(()=>t.posts.length).toBe(1);expect(t.posts[0]).toEqual({});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);
});


test('the default contract workflow preserves fractional-cent fees while the actual debit remains whole cents',async({page})=>{
 const placed:Record<string,unknown>[]=[];await page.route('**/api/auth',route=>route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({user:{id:'SYNTHETIC-FRACTIONAL-FEE-OWNER',email:'synthetic-fee@example.test'}})}));await page.route('**/api/ledger',route=>route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({accounts:[],transactions:[],chart:[],bets:[],summary:{cashBalanceCents:100000,realizedPlCents:0}})}));await page.route('**/api/bets',route=>{placed.push(route.request().postDataJSON());return route.fulfill({status:201,contentType:'application/json',body:JSON.stringify({id:'SYNTHETIC-FRACTIONAL-FEE-WAGER'})});});
 await page.goto('/#bankroll');await page.getByRole('button',{name:'Record wager',exact:true}).click();await expect(page.getByLabel('Record type',{exact:true})).toHaveValue('event_contract');await page.getByLabel('Event',{exact:true}).fill('SYNTHETIC one-cent debit');await page.getByLabel('Market',{exact:true}).fill('SYNTHETIC contract');await page.getByLabel('Selection',{exact:true}).fill('SYNTHETIC YES');await page.getByLabel('Contract price (cents)',{exact:true}).fill('0.1');await page.getByLabel('Amount spent including fees (USD)',{exact:true}).fill('0.01');await page.getByLabel('Contract quantity (optional)',{exact:true}).fill('1');await page.getByLabel('Total entry fees (cents)',{exact:true}).fill('0.9');await page.getByRole('button',{name:'Save record',exact:true}).click();
 await expect(page.getByRole('dialog')).toHaveCount(0);expect(placed).toHaveLength(1);expect(placed[0]).toMatchObject({marketInstrument:'event_contract',contractPriceCents:'0.1',entryFeeCents:'0.9',stake:'0.01',contractQuantity:1});expect(placed[0]).not.toHaveProperty('odds');
});
