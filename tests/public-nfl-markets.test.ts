import {afterEach,describe,expect,it,vi} from 'vitest';
import {fetchPublicMarkets,kalshiEventTicker,normalizeKalshiMarkets,valuePublicMarkets,KALSHI_PUBLIC_API,KALSHI_SERIES_URL} from '../lib/public-nfl/markets';
import type {PublicGame} from '../lib/public-nfl/types';

// SYNTHETIC transport/mechanics fixtures; never seeded or presented as live prices.
const game:PublicGame={id:'2026_09_BAL_BUF',season:2026,week:9,startTime:'2026-11-01T18:00:00Z',status:'scheduled',away:{id:'BAL',abbreviation:'BAL',name:'Baltimore Ravens'},home:{id:'BUF',abbreviation:'BUF',name:'Buffalo Bills'},sources:[]};
const checkedAt='2026-10-30T19:00:00Z',event='KXNFLGAME-26NOV01BALBUF';
const series={series:{ticker:'KXNFLGAME',contract_terms_url:'https://assets.kalshi.com/contract_terms/FOOTBALLGAMEWIN.pdf',fee_type:'quadratic_with_maker_fees',fee_multiplier:1}};
function fixture(team='BUF'){
 const name=team==='BUF'?'Buffalo':'Baltimore';
 return{ticker:event+'-'+team,event_ticker:event,market_type:'binary',status:'active',title:name+' wins',yes_sub_title:name,notional_value_dollars:'1.0000',yes_ask_dollars:'0.6200',yes_bid_dollars:'0.6100',yes_ask_size_fp:'12.50',yes_bid_size_fp:'10.00',no_ask_dollars:'0.3900',no_bid_dollars:'0.3800',open_interest_fp:'120.50',volume_fp:'500.00',updated_time:'2026-10-20T04:06:00Z',rules_primary:`If ${name} wins the Baltimore vs Buffalo Pro Football game originally scheduled for Nov 1, 2026, then the market resolves to Yes.`,rules_secondary:'The following market refers to the team who wins the Baltimore vs Buffalo Pro Football game originally scheduled for Nov 1, 2026. If the game ends in a tie, the market will resolve to $0.50 for each team. If the game is postponed but begins within 48 hours from its originally scheduled start time, the market will remain open and resolve based on the official final result. If the game is not started within 48 hours, the market will resolve to a fair price.'};
}
const normalize=(markets:any[],meta:any=series)=>normalizeKalshiMarkets(game,{cursor:'',markets},meta,checkedAt,'https://external-api.kalshi.com/trade-api/v2/markets?event_ticker='+event);
afterEach(()=>vi.unstubAllGlobals());
describe('Authorized public alternative NFL contracts',()=>{
 it('uses the Eastern scheduled game date and keeps Los Angeles identities distinct',()=>{
  expect(kalshiEventTicker({...game,startTime:'2026-11-02T01:20:00Z'})).toBe(event);
  expect(kalshiEventTicker({...game,away:{...game.away,id:'LAC'},home:{...game.home,id:'LA'}})).toBe('KXNFLGAME-26NOV01LACLAR');
 });
 it('preserves exact observed quotes, independent provider, full rules and unknown DraftKings equivalence',()=>{
  const result=normalize([fixture(),fixture('BAL')]);expect(result.status).toBe('partial');expect(result.items).toHaveLength(2);
  const item=result.items[0];expect(item.yesAskCents).toBe('62');expect(item.yesBidCents).toBe('61');expect(item.provider).toBe('Kalshi');expect(item.draftKingsEquivalent).toBe(false);expect(item.definition.tiePayoutCents).toBe(50);expect(item.rules).toContain('within 48 hours');expect(item.expectedNetValueAfterFeesCents).toBeNull();expect(result.message).toMatch(/DraftKings.*unavailable/);
  expect(item.observedAt).toBe(checkedAt);expect(item.quotedAt).toBeNull();expect(item.sourceUpdatedAt).not.toBe(item.observedAt);expect(item.quoteTimestampMeaning).toMatch(/not a verified quote timestamp/);
 });
 it('withholds wrong events, team/date mismatch, missing rules and incompatible tie settlement',()=>{
  for(const changed of [{event_ticker:'KXNFLGAME-26NOV08BALBUF'},{ticker:event+'-NYG'},{yes_sub_title:'Baltimore'},{rules_primary:fixture().rules_primary.replace('Nov 1','Nov 8')},{rules_secondary:''},{rules_secondary:fixture().rules_secondary.replace('$0.50','$1.00')}])expect(normalize([{...fixture(),...changed}]).items).toHaveLength(0);
 });
 it('never publishes a zero/empty ask as an executable price and does not infer size from opposite quotes',()=>{
  const result=normalize([{...fixture(),yes_ask_dollars:'0.0000',yes_ask_size_fp:'100.00'}]);expect(result.items[0].yesAskCents).toBeUndefined();expect(result.items[0].yesBidCents).toBe('61');expect(result.items[0].executionVerified).toBe(false);
  expect(normalize([{...fixture(),yes_ask_size_fp:'0.00',yes_bid_size_fp:'0.00'}]).items).toHaveLength(0);
  expect(normalize([{...fixture(),yes_ask_dollars:'NaN',yes_bid_dollars:'invalid'}]).items).toHaveLength(0);
  expect(normalize([{...fixture(),yes_bid_dollars:'0.7000'}]).items).toHaveLength(0);
 });
 it('retains verified quotes when the exact fee calculation is unknown but withholds net EV',()=>{
  const result=normalize([fixture()],{series:{ticker:'KXNFLGAME'}});expect(result.items[0].fees).toMatchObject({type:null,multiplier:null,calculationStatus:'not_verified',entryFeeCents:null});expect(result.items[0].expectedNetValueAfterFeesCents).toBeNull();
 });
 it('computes a conditional 50-cent tie payout from the same simulated game outcomes without calling it net EV',()=>{
  const valued=valuePublicMarkets(normalize([fixture()]),{simulations:10000,home:'BUF',away:'BAL',eventStart:game.startTime,homeWinProbability:.6,awayWinProbability:.38,tieProbability:.02}).items[0];
  expect(valued.modelProbability).toBe(.6);expect(valued.tieProbability).toBe(.02);expect(valued.modelExpectedSettlementCents).toBe('61');expect(valued.expectedNetValueAfterFeesCents).toBeNull();expect(valued.valuationMessage).toMatch(/Postponement.*unvalued/);
 });
 it('does not attach a different game or invalid probability vector to a contract',()=>{
  for(const result of [{simulations:10000,home:'BUF',away:'BAL',eventStart:'2026-11-08T18:00:00Z',homeWinProbability:.6,awayWinProbability:.38,tieProbability:.02},{simulations:10000,home:'BUF',away:'BAL',eventStart:game.startTime,homeWinProbability:.6,awayWinProbability:.6,tieProbability:.02}])expect(valuePublicMarkets(normalize([fixture()]),result).items[0].modelExpectedSettlementCents).toBeUndefined();
 });
 it('keeps semantic settlement definitions unchanged when quoted prices or observation times change',()=>{
  const a=normalize([fixture()]).items[0],b=normalizeKalshiMarkets(game,{cursor:'',markets:[{...fixture(),yes_ask_dollars:'0.7000',updated_time:'2026-10-30T20:00:00Z'}]},series,'2026-10-30T21:00:00Z','https://example.invalid/synthetic').items[0];expect(a.definition).toEqual(b.definition);expect(a.rules).toBe(b.rules);expect(a.yesAskCents).not.toBe(b.yesAskCents);
 });
 it('uses only documented unauthenticated read-only endpoints and gracefully handles failed sources',async()=>{
  const calls:string[]=[];vi.stubGlobal('fetch',vi.fn(async(url:any,init:any)=>{calls.push(String(url));expect(init.method).toBe('GET');expect(init.headers.Authorization).toBeUndefined();return Response.json(String(url)===KALSHI_SERIES_URL?series:{cursor:'',markets:[fixture()]});}));
  const result=await fetchPublicMarkets(game);expect(result.items).toHaveLength(1);expect(calls.every(url=>url.startsWith(KALSHI_PUBLIC_API+'/'))).toBe(true);
  const again=await fetchPublicMarkets(game);expect(again.checkedAt).toBe(result.checkedAt);expect(calls).toHaveLength(2);
  vi.stubGlobal('fetch',vi.fn(async()=>new Response('Unavailable',{status:503})));const unavailable=await fetchPublicMarkets(game,{force:true});expect(unavailable.status).toBe('unavailable');expect(unavailable.items).toEqual([]);
 });
});
