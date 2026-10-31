/** SYNTHETIC browser transports only. No production market, forecast or account data. */
import {test,expect,type Page} from '@playwright/test';
import {playerPropFixture} from './fixtures/player-props';

async function transport(page:Page,{authorized=false,expiresSoon=false,unavailable=false,staleQuotedAt=false,kickoffSoon=false}={}){
 const fixture=playerPropFixture(),queries:URLSearchParams[]=[],posts:unknown[]=[],postProviders:string[]=[],saves:unknown[]=[],now=new Date().toISOString();
 const definition={...structuredClone(fixture.receiverYes.contract),id:'SYNTHETIC-V7-TOTAL',contractId:'SYNTHETIC-V7-TOTAL',provider:'DraftKings Predictions',sourceKind:'authorized_feed',playerId:null,playerName:'SYNTHETIC matchup total',providerPlayerId:null,position:null,subject:{kind:'game',teamId:null},eventStart:kickoffSoon?new Date(Date.now()+6000).toISOString():fixture.nfl.game.startTime,stat:'totalPoints',category:'totalPoints',threshold:49.5,operator:'gt',title:'SYNTHETIC total points above 49.5',displayedYesPercent:'63',displayedNoPercent:'37',yesAskCents:'65',noAskCents:'37',settlement:{...fixture.receiverYes.contract.settlement,nonParticipationPolicy:'stat_zero',unconditionalValuationSupported:true,statCoverage:'SYNTHETIC full-game scores including overtime',reason:'SYNTHETIC supported completion rules'},fees:{...fixture.receiverYes.contract.fees,calculationStatus:'verified_explicit',entryFeeCents:'1',winFeeCents:'0',rounding:'none',reason:'SYNTHETIC explicitly verified fee fixture'},quotedAt:staleQuotedAt?new Date(Date.now()-125000).toISOString():null,observedAt:expiresSoon?new Date(Date.now()-114000).toISOString():now};
 const result={...structuredClone(fixture.receiverYes),id:'SYNTHETIC-V7-RESEARCH',contract:definition,currentContract:{...structuredClone(definition),displayedYesPercent:'67',displayedNoPercent:'33',yesAskCents:'68',noAskCents:'34'},player:{id:null,name:'SYNTHETIC matchup total',team:'SYN-A',position:null},status:'available',probability:{...fixture.receiverYes.probability,raw:.8,calibrated:null,conditional:false,condition:null,modelInterval95:[.65,.89]},valuation:{breakEven:.69,fairCents:'80',netValueCents:'11',entryCostCents:'69',feesVerified:true,reason:'SYNTHETIC fee-aware comparison'},distribution:{...fixture.receiverYes.distribution,histogram:[{value:40,count:2000},{value:50,count:3000},{value:60,count:5000}]},rankingMetrics:{calibratedProbability:null,modelMarketDifference:.12,historicalSupport:null,uncertaintyWidth:.24,injuryChange:null,priceChange:null}};
 const providers=fixture.scan.providers.map(value=>value.provider==='DraftKings Predictions'?{...value,status:authorized?'available':'unavailable',contracts:authorized?1:0,message:authorized?'SYNTHETIC authorized DraftKings Predictions source; no real production access claimed.':'SYNTHETIC authorized DraftKings Predictions feed unavailable. Another platform is not substituted.'}:value);
 const base={...fixture.scan,runId:'SYNTHETIC-V7-RUN',resultSetId:'SYNTHETIC-V7-PHYSICAL-SET',providers,results:[],totalResults:0,nextCursor:null,progress:{completed:2,total:2,phase:'completed',gamesComplete:1,gamesTotal:1}};
 await page.route('**/api/auth',route=>route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({user:null})}));
 await page.route('**/api/nfl**',route=>{
  const request=route.request(),url=new URL(request.url()),path=url.pathname,reply=(body:unknown,status=200)=>route.fulfill({status,contentType:'application/json',body:JSON.stringify(body)});
  if(path==='/api/nfl')return reply(fixture.nfl.dashboard);
  if(path==='/api/nfl/markets/analyze'){posts.push(request.postDataJSON());postProviders.push(url.searchParams.get('provider')??'DraftKings Predictions');if(!authorized&&url.searchParams.get('provider')!=='Kalshi')return reply({...base,status:'unavailable',runId:null,progress:{completed:0,total:0,phase:'SYNTHETIC authorized DraftKings feed unavailable',gamesComplete:0,gamesTotal:0}});return reply({...base,status:'queued',progress:{...base.progress,completed:0,phase:'Checking authorized event contracts'}},202);}
  if(path==='/api/nfl/markets'){
   queries.push(url.searchParams);if(unavailable)return reply({error:'SYNTHETIC upstream market service is unavailable.'},503);
   const alternative=url.searchParams.get('provider')==='Kalshi';
   return reply({...base,results:alternative?[fixture.receiverYes]:authorized?[result]:[],totalResults:alternative||authorized?1:0});
  }
  if(path==='/api/nfl/markets/results/'+result.id)return reply({research:result});
  if(path==='/api/nfl/markets/results/'+fixture.receiverYes.id)return reply({research:fixture.receiverYes});
  if(path==='/api/nfl/markets/save'){saves.push(request.postDataJSON());return reply({error:'SYNTHETIC identity required'},401);}
  return reply({error:'SYNTHETIC route not provided'},404);
 });
 await page.route('**/api/props**',route=>route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({jobs:[],private:true})}));
 return{fixture,result,queries,posts,postProviders,saves,base};
}

test('the primary platform remains DraftKings Predictions and an alternative is shown only after an explicit choice',async({page})=>{
 const t=await transport(page);await page.goto('/');
 await expect(page.locator('.bottom-nav').getByText('NFL',{exact:true})).toHaveCount(1);
 await page.getByRole('button',{name:'ANALYZE ALL NFL MARKETS',exact:true}).click();await expect(page.getByRole('heading',{name:'Every market. The exact contract.'})).toBeVisible();
 await expect.poll(()=>t.posts.length).toBe(1);expect(t.posts[0]).toEqual({});
 await expect(page.getByRole('heading',{name:'DraftKings Predictions data unavailable.'})).toBeVisible({timeout:15000});
 await expect(page.locator('.market-source-explanation')).toContainText('Another platform is not substituted.');await expect(page.locator('[data-testid^="prop-research-"]')).toHaveCount(0);
 await page.getByRole('button',{name:'Explore separately labeled Kalshi research'}).click();await expect(page.getByTestId('prop-research-'+t.fixture.receiverYes.id)).toBeVisible();
 await expect(page.locator('.market-source-explanation')).toContainText('You selected Kalshi research');await expect(page.getByTestId('prop-research-'+t.fixture.receiverYes.id)).toContainText('Separate platform · not a DraftKings quote');
 expect(t.queries.some(query=>query.get('provider')==='Kalshi')).toBe(true);await page.getByRole('button',{name:'ANALYZE ALL NFL MARKETS',exact:true}).click();await expect.poll(()=>t.posts.length).toBe(2);expect(t.postProviders).toEqual(['DraftKings Predictions','Kalshi']);await page.reload();await expect(page.getByTestId('prop-research-'+t.fixture.receiverYes.id)).toBeVisible();expect(t.posts).toHaveLength(2);
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);await page.screenshot({path:`test-results/v7-${test.info().project.name}-primary-unavailable.png`,fullPage:false});
});

test('a game contract keeps displayed percentage, observed ask and fee-aware valuation distinct',async({page})=>{
 const t=await transport(page,{authorized:true});await page.goto('/#markets');const card=page.getByTestId('prop-research-'+t.result.id);await expect(card).toBeVisible();
 await expect(card.locator('.prop-displayed-price')).toContainText('67%');await expect(card.locator('.prop-price-grid')).toContainText('68¢');await expect(card.locator('.prop-price-grid')).toContainText('69.0%');await expect(card.locator('.prop-price-grid')).toContainText('11¢');
 await expect(card.locator('.prop-probability-row')).toContainText('80.0%');await expect(card.locator('.prop-calibrated')).toContainText('Unavailable');await expect(card).toContainText('Simulated game outcomes');await expect(card).toContainText('Game-contract combinations require additional settlement verification');await expect(card.getByRole('checkbox')).toBeDisabled();
 await card.getByText('Exact contract and settlement rules',{exact:true}).click();await expect(card).toContainText('SYNTHETIC-V7-TOTAL');await expect(card).toContainText('49.5');
 await page.getByLabel('NFL market category').selectOption('totalPoints');await expect.poll(()=>t.queries.at(-1)?.get('category')).toBe('totalPoints');await page.getByLabel('NFL market ranking').selectOption('calibrated');await expect.poll(()=>t.queries.at(-1)?.get('ranking')).toBe('calibrated');await expect(page.locator('.market-ranking-note')).toContainText('Unsupported estimates remain unavailable');
 await card.getByRole('button',{name:'Save to my research',exact:true}).click();await expect(page.getByRole('dialog')).toContainText('YOUR GRIDIRON AI ACCOUNT');expect(t.saves).toEqual([]);await page.getByRole('button',{name:'Close sign in',exact:true}).click();
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);await page.screenshot({path:`test-results/v7-${test.info().project.name}-game-contract.png`,fullPage:true});
});

test('a visible quote expires without waiting for the next dashboard refresh and stale net value is withheld',async({page})=>{
 const t=await transport(page,{authorized:true,expiresSoon:true});await page.goto('/#markets');const card=page.getByTestId('prop-research-'+t.result.id);await expect(card).toBeVisible();await expect(card.locator('.prop-card-source')).toContainText('OBSERVED QUOTE');
 await expect(card.locator('.prop-card-source')).toContainText('HISTORICAL QUOTE',{timeout:10000});await expect(card).toContainText('Current quote freshness is not verified');await expect(card.locator('.prop-price-grid')).not.toContainText('11¢');await expect(card.locator('.prop-price-grid')).not.toContainText('69.0%');await expect(card.locator('.prop-probability-row')).toContainText('80.0%');
});

test('a failed all-NFL feed stays a clear error with working retry rather than fake markets or a sign-in redirect',async({page})=>{
 await transport(page,{unavailable:true});await page.goto('/#markets');await expect(page.getByRole('alert').filter({hasText:'SYNTHETIC upstream market service is unavailable.'})).toBeVisible();await expect(page.getByRole('dialog')).toHaveCount(0);await expect(page.locator('[data-testid^="prop-research-"]')).toHaveCount(0);await expect(page.getByRole('button',{name:'Retry',exact:true})).toBeEnabled();expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);
});


test('a fresh collection timestamp cannot revive an expired authorized source quote',async({page})=>{
 const t=await transport(page,{authorized:true,staleQuotedAt:true});await page.goto('/#markets');const card=page.getByTestId('prop-research-'+t.result.id);await expect(card).toBeVisible();
 await expect(card.locator('.prop-card-source')).toContainText('HISTORICAL QUOTE');await expect(card.locator('.prop-price-grid')).not.toContainText('11¢');await expect(card).toContainText('Current quote freshness is not verified');await expect(card.locator('.prop-probability-row')).toContainText('80.0%');
});

test('new automatic research preserves an open immutable snapshot and its in-flight explanation',async({page})=>{
 const t=await transport(page,{authorized:true});let changed=false;const fresh={...structuredClone(t.result),id:'SYNTHETIC-V7-NEW-RESEARCH',probability:{...t.result.probability,raw:.65}};
 await page.route(/\/api\/nfl\/markets(?:\?.*)?$/,route=>route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({...t.base,status:changed?'completed':'running',results:[changed?fresh:t.result],totalResults:1})}));
 await page.route('**/api/props/assistant',async route=>{changed=true;await new Promise(resolve=>setTimeout(resolve,6500));return route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({summary:{text:'SYNTHETIC explanation for the immutable original 80% estimate.',generatedByAI:false,citations:[]}})});});
 await page.goto('/#markets');const oldCard=page.getByTestId('prop-research-'+t.result.id);await expect(oldCard).toBeVisible();await oldCard.getByLabel('Question about SYNTHETIC total points above 49.5 contract').fill('SYNTHETIC explain this original estimate.');await oldCard.getByRole('button',{name:'Explain',exact:true}).click();
 await expect(page.getByTestId('prop-research-'+fresh.id)).toBeVisible({timeout:15000});await expect(oldCard).toBeVisible();await expect(oldCard).toContainText('New research arrived. This open snapshot is preserved as historical');await expect(oldCard.locator('.prop-assistant-answer')).toContainText('immutable original 80% estimate',{timeout:15000});await expect(oldCard.locator('.prop-probability-row')).toContainText('80.0%');await expect(page.getByTestId('prop-research-'+fresh.id).locator('.prop-probability-row')).toContainText('65.0%');
});


test('kickoff ends current price comparisons and labels the pregame simulation historical',async({page})=>{
 const t=await transport(page,{authorized:true,kickoffSoon:true});await page.goto('/#markets');const card=page.getByTestId('prop-research-'+t.result.id);await expect(card).toBeVisible();await expect(card.locator('.prop-card-source')).toContainText('OBSERVED QUOTE');
 await expect(card.locator('.prop-card-source')).toContainText('HISTORICAL QUOTE',{timeout:12000});await expect(card.locator('.prop-probability-row')).toContainText('Historical simulation estimate');await expect(card.locator('.prop-price-grid')).not.toContainText('11¢');await expect(card.locator('.prop-probability-row')).toContainText('80.0%');
});

test('a winner contract shows partial tie payments separately from its full-payout probability and model audit',async({page})=>{
 const t=await transport(page,{authorized:true});const contract={...t.result.contract,stat:'gameWinner',category:'gameWinner',threshold:0,title:'SYNTHETIC away team wins',subject:{kind:'team',teamId:'SYN-A'},settlement:{...t.result.contract.settlement,tiePayoutCents:'50',unconditionalValuationSupported:false}};
 Object.assign(t.result,{contract,currentContract:contract,probability:{...t.result.probability,raw:.49,conditional:true},valuation:{...t.result.valuation,fairCents:null,netValueCents:null,breakEven:null},distribution:{...t.result.distribution,histogram:[{value:-7,count:5000},{value:0,count:100},{value:7,count:4900}],mean:-.07},settlementEstimate:{winProbability:.49,lossProbability:.5,tieProbability:.01,tiePayoutCents:'50',expectedSettlementCents:'49.500000',condition:'SYNTHETIC normal-completion scenario only; exceptional settlements remain unsupported.'}});
 t.base.performance={gameMarkets:{n:0,brier:null,logLoss:null,message:'SYNTHETIC game-contract audit is separate from player forecasts.'},playerMarkets:t.fixture.scan.performance};
 await page.goto('/#markets');const card=page.getByTestId('prop-research-'+t.result.id);await expect(card).toBeVisible();await expect(card.locator('.prop-probability-row')).toContainText('Full-payout simulation probability');await expect(card.locator('.prop-probability-row')).toContainText('49.0%');
 const settlement=card.locator('.prop-settlement-estimate');await expect(settlement).toContainText('1.0%');await expect(settlement).toContainText('50¢');await expect(settlement).toContainText('49.5¢');await expect(settlement).toContainText('need not sum to 100%');await expect(page.locator('.props-performance')).toHaveCount(2);await expect(page.locator('.props-performance').first()).toContainText('GAME CONTRACT MODEL AUDIT');await expect(page.locator('.props-performance').last()).toContainText('PLAYER PROP MODEL LAB');
});
