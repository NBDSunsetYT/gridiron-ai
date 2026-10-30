import Decimal from 'decimal.js';
import {boundedFetch,source} from './sources';
import type {PublicCoverage,PublicGame,ResearchSource} from './types';

/** Kalshi explicitly documents these unauthenticated, read-only endpoints.
 * This module never authenticates, sends orders, or substitutes its prices for
 * DraftKings. Unknown settlement/fee equivalence with DraftKings stays unknown.
 */
export const KALSHI_PUBLIC_API='https://external-api.kalshi.com/trade-api/v2';
export const KALSHI_MARKET_DATA_DOCS='https://docs.kalshi.com/getting_started/quick_start_market_data';
export const KALSHI_SERIES_URL=KALSHI_PUBLIC_API+'/series/KXNFLGAME';
const MONTHS=['JAN','FEB','MAR','APR','MAY','JUN','JUL','AUG','SEP','OCT','NOV','DEC'];
const coverageCache=new Map<string,{until:number;value:PublicCoverage<Record<string,any>>}>();
const pending=new Map<string,Promise<PublicCoverage<Record<string,any>>>>();
const LABELS:Record<string,string>={ARI:'Arizona',ATL:'Atlanta',BAL:'Baltimore',BUF:'Buffalo',CAR:'Carolina',CHI:'Chicago',CIN:'Cincinnati',CLE:'Cleveland',DAL:'Dallas',DEN:'Denver',DET:'Detroit',GB:'Green Bay',HOU:'Houston',IND:'Indianapolis',JAX:'Jacksonville',KC:'Kansas City',LA:'Los Angeles R',LAR:'Los Angeles R',LAC:'Los Angeles C',LV:'Las Vegas',MIA:'Miami',MIN:'Minnesota',NE:'New England',NO:'New Orleans',NYG:'New York G',NYJ:'New York J',PHI:'Philadelphia',PIT:'Pittsburgh',SEA:'Seattle',SF:'San Francisco',TB:'Tampa Bay',TEN:'Tennessee',WAS:'Washington'};
const code=(id:string)=>id==='LA'?'LAR':id;
const compact=(value:unknown)=>typeof value==='string'?value.replace(/\s+/g,' ').trim():'';
function decimal(value:unknown,max?:number){
 if(typeof value!=='string'||!/^\d+(?:\.\d{1,8})?$/.test(value))return null;
 const parsed=new Decimal(value);return parsed.isFinite()&&parsed.gte(0)&&(max===undefined||parsed.lte(max))?parsed:null;
}
function quote(price:unknown,size:unknown){const p=decimal(price,1),s=decimal(size);return p?.gt(0)&&s?.gt(0)?p.mul(100).toString():undefined;}
function dateParts(game:PublicGame){
 if(!Number.isFinite(Date.parse(game.startTime))||!LABELS[game.home.id]||!LABELS[game.away.id]||game.home.id===game.away.id)return null;
 const parts=Object.fromEntries(new Intl.DateTimeFormat('en-US',{timeZone:'America/New_York',year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(new Date(game.startTime)).map(p=>[p.type,p.value]));
 return{year:parts.year,month:Number(parts.month),day:Number(parts.day)};
}
export function kalshiEventTicker(game:PublicGame){const d=dateParts(game);return d?`KXNFLGAME-${d.year.slice(-2)}${MONTHS[d.month-1]}${String(d.day).padStart(2,'0')}${code(game.away.id)}${code(game.home.id)}`:null;}
function unavailable(checkedAt:string,sources:ResearchSource[],message='An authorized matching live contract could not be verified right now. DraftKings Predictions prices remain unavailable; no replacement price is invented.'):PublicCoverage<Record<string,any>>{return{status:'unavailable',items:[],checkedAt,message,sources};}

export function normalizeKalshiMarkets(game:PublicGame,body:unknown,seriesBody:unknown,checkedAt:string,marketsUrl:string):PublicCoverage<Record<string,any>>{
 const event=kalshiEventTicker(game),d=dateParts(game),data=body as any,series=(seriesBody as any)?.series;
 const sources=[source('kalshi-public-markets','Kalshi published NFL contract quotes',marketsUrl,checkedAt,'partial','Observed public quotes; no authenticated order or guaranteed fill is claimed.'),source('kalshi-public-series','Kalshi NFL contract and fee metadata',KALSHI_SERIES_URL,checkedAt,'partial','The series publishes a fee type and multiplier. Exact fee coefficient/rounding is not independently verified here; net EV is withheld.'),source('kalshi-public-api-docs','Kalshi public market-data API documentation',KALSHI_MARKET_DATA_DOCS,checkedAt)];
 if(!event||!d||!Array.isArray(data?.markets)||data.cursor||series?.ticker!=='KXNFLGAME')return unavailable(checkedAt,sources);
 const termsUrl=typeof series.contract_terms_url==='string'&&series.contract_terms_url.startsWith('https://assets.kalshi.com/')?series.contract_terms_url:null;
 const feeType=typeof series.fee_type==='string'&&series.fee_type.length<=100?series.fee_type:null;
 const feeMultiplier=typeof series.fee_multiplier==='number'&&Number.isFinite(series.fee_multiplier)&&series.fee_multiplier>=0?String(series.fee_multiplier):null;
 const items:Record<string,any>[]=[];
 for(const market of data.markets){
  if(!market||market.event_ticker!==event||market.market_type!=='binary'||!['active','open'].includes(market.status)||decimal(market.notional_value_dollars,1)?.eq(1)!==true)continue;
  const team=[game.home.id,game.away.id].find(id=>market.ticker===event+'-'+code(id));if(!team)continue;
  const label=LABELS[team],away=LABELS[game.away.id],home=LABELS[game.home.id];
  const date=`${MONTHS[d.month-1][0]}${MONTHS[d.month-1].slice(1).toLowerCase()} ${d.day}, ${d.year}`;
  const expected=`If ${label} wins the ${away} vs ${home} Pro Football game originally scheduled for ${date}, then the market resolves to Yes.`;
  const primary=compact(market.rules_primary),secondary=compact(market.rules_secondary);
  if(compact(market.yes_sub_title)!==label||primary!==expected||!secondary.includes('If the game ends in a tie, the market will resolve to $0.50 for each team.')||!secondary.includes('within 48 hours')||!secondary.includes('market will resolve to a fair price.'))continue;
  const yesAsk=quote(market.yes_ask_dollars,market.yes_ask_size_fp),yesBid=quote(market.yes_bid_dollars,market.yes_bid_size_fp);
  if(yesAsk!==undefined&&yesBid!==undefined&&new Decimal(yesBid).gt(yesAsk))continue;
  // NO sizes are not present in this public summary. Opposite-side liquidity
  // cannot be asserted; retain quoted prices separately from verified sizes.
  const noAsk=decimal(market.no_ask_dollars,1)?.mul(100).toString(),noBid=decimal(market.no_bid_dollars,1)?.mul(100).toString();
  if(yesAsk===undefined&&yesBid===undefined)continue;
  const definition={kind:'game_winner',gameId:game.id,homeTeamId:game.home.id,awayTeamId:game.away.id,startsAt:game.startTime,team,side:'YES',tiePayoutCents:50,normalCompletionOnly:true,postponementPolicy:'48h_then_fair_price'};
  items.push({id:market.ticker,contractId:market.ticker,eventId:market.event_ticker,provider:'Kalshi',source:'Kalshi public market-data API',sourceUrl:marketsUrl,title:market.title,question:market.title,team,threshold:null,side:'YES',yesAskCents:yesAsk,yesBidCents:yesBid,noAskCents:noAsk,noBidCents:noBid,quotedAt:null,observedAt:checkedAt,updatedAt:checkedAt,sourceUpdatedAt:typeof market.updated_time==='string'?market.updated_time:null,quoteTimestampMeaning:'Observed at collection; an exchange quote-change timestamp was not supplied. Market updated_time is metadata, not a verified quote timestamp.',verified:true,quoteVerified:true,executionVerified:false,yesAskSize:decimal(market.yes_ask_size_fp)?.toString()??null,yesBidSize:decimal(market.yes_bid_size_fp)?.toString()??null,openInterest:decimal(market.open_interest_fp)?.toString()??null,volume:decimal(market.volume_fp)?.toString()??null,liquidityMeaning:'Displayed public size can change before execution; no fill is guaranteed.',fees:{type:feeType,multiplier:feeMultiplier,calculationStatus:'not_verified',entryFeeCents:null,sourceUrl:KALSHI_SERIES_URL},rules:primary+'\n\n'+secondary,settlementRule:primary+'\n\n'+secondary,rulesUrl:termsUrl,definition,draftKingsEquivalent:false,draftKingsComparisonStatus:'unverified_DraftKings_contract_rules_unavailable',comparisonEligibility:'normal_completion_only',expectedNetValueAfterFeesCents:null,valuationMessage:'DraftKings equivalence, exact fees and exceptional-event valuation are unverified. Fee-aware net EV is withheld.'});
 }
 if(!items.length)return unavailable(checkedAt,sources,'No open Kalshi contract with verified matchup identity, displayed quotes and supported settlement rules was found. DraftKings Predictions prices remain unavailable.');
 return{status:'partial',items,checkedAt,message:'Verified Kalshi NFL contract quotes are shown as a separate authorized public alternative. DraftKings Predictions prices and exact settlement equivalence are unavailable. Fees and exceptional settlement terms prevent a verified net-EV claim.',sources};
}

export async function fetchPublicMarkets(game:PublicGame,options:{force?:boolean}={}):Promise<PublicCoverage<Record<string,any>>>{
 const checkedAt=new Date().toISOString(),event=kalshiEventTicker(game);
 if(!event)return unavailable(checkedAt,[]);
 const key=[event,game.id,game.home.id,game.away.id,game.startTime].join(':');
 const cached=coverageCache.get(key);if(!options.force&&cached&&cached.until>Date.now())return cached.value;
 if(pending.has(key))return pending.get(key)!;
 if(pending.size>=32)return unavailable(checkedAt,[],'The public market source is busy. Previously observed quotes remain historical; no new price was invented.');
 const url=`${KALSHI_PUBLIC_API}/markets?event_ticker=${encodeURIComponent(event)}&status=open&limit=100`;
 const task=(async()=>{let value:PublicCoverage<Record<string,any>>;
  try{const [markets,series]=await Promise.all([boundedFetch(url,1_000_000,8000),boundedFetch(KALSHI_SERIES_URL,100_000,8000)]);value=normalizeKalshiMarkets(game,JSON.parse(markets.body.toString('utf8')),JSON.parse(series.body.toString('utf8')),checkedAt,url);}
  catch{value=unavailable(checkedAt,[source('kalshi-public-markets','Kalshi published NFL contract quotes',url,checkedAt,'unavailable')]);}
  if(coverageCache.size>=32)coverageCache.delete(coverageCache.keys().next().value!);
  coverageCache.set(key,{until:Date.now()+60000,value});return value;
 })().finally(()=>pending.delete(key));pending.set(key,task);return task;
}

/** Expected payout under the complete game's normal win/tie/loss outcomes.
 * This is neither a DraftKings valuation nor net EV: postponement/fair-price
 * scenarios and the exact trading fee calculation are not modeled.
 */
export function valuePublicMarkets(coverage:PublicCoverage<Record<string,any>>,result?:Record<string,any>|null):PublicCoverage<Record<string,any>>{
 if(!result||!Number.isInteger(result.simulations)||result.simulations<10000)return coverage;
 const p=[result.homeWinProbability,result.awayWinProbability,result.tieProbability];
 if(p.some(value=>!Number.isFinite(value)||value<0||value>1)||Math.abs(p.reduce((n,v)=>n+v,0)-1)>1e-8)return coverage;
 return{...coverage,items:coverage.items.map(item=>{
  const d=item.definition;if(!d||d.homeTeamId!==result.home||d.awayTeamId!==result.away||Date.parse(d.startsAt)!==Date.parse(result.eventStart)||d.tiePayoutCents!==50)return item;
  const win=d.team===result.home?p[0]:d.team===result.away?p[1]:null;if(win===null)return item;
  return{...item,modelProbability:win,tieProbability:p[2],modelExpectedSettlementCents:new Decimal(win).mul(100).add(new Decimal(p[2]).mul(50)).toDecimalPlaces(6).toString(),expectedNetValueAfterFeesCents:null,valuationMessage:'Expected settlement assumes this scheduled game completes normally: 100¢ for a win, 50¢ for a tie, 0¢ for a loss. Postponement/fair-price scenarios and exact fees remain unvalued; no net-EV or DraftKings-equivalence claim is made.'};
 })};
}
