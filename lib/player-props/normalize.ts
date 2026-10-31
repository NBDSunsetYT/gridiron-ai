import Decimal from 'decimal.js';
import {sha} from '../public-nfl/sources';
import type {PublicGame} from '../public-nfl/types';
import {isGameMarket,type PropMarketContract,type PropPlayerIdentity,type PropStat,type PropFees} from './market-types';

/** Only full-game, scalar player markets are eligible. Defensive interceptions,
 * ladders, protected contracts and period-specific products are different rules. */
export const KALSHI_PROP_SERIES:Array<{ticker:string;stat:PropStat;category:string;wording:string}>=
 [
  {ticker:'KXNFLPASSYDS',stat:'passingYards',category:'Passing yards',wording:'passing yards'},
  {ticker:'KXNFLPASSTDS',stat:'passingTouchdowns',category:'Passing touchdowns',wording:'passing touchdowns'},
  {ticker:'KXNFLPASSATT',stat:'passingAttempts',category:'Passing attempts',wording:'passing attempts'},
  {ticker:'KXNFLPASSCOMP',stat:'completions',category:'Passing completions',wording:'passing completions'},
  {ticker:'KXNFLPASSINT',stat:'interceptions',category:'Interceptions thrown',wording:'passing interceptions'},
  {ticker:'KXNFLRSHYDS',stat:'rushingYards',category:'Rushing yards',wording:'rushing yards'},
  {ticker:'KXNFLRSHATT',stat:'carries',category:'Rushing attempts',wording:'rushing attempts'},
  {ticker:'KXNFLRECYDS',stat:'receivingYards',category:'Receiving yards',wording:'receiving yards'},
  {ticker:'KXNFLREC',stat:'receptions',category:'Receptions',wording:'receptions'},
  {ticker:'KXNFLTD',stat:'touchdowns',category:'Touchdowns',wording:'touchdowns'},
 ];
export const FOOTBALL_TERMS_URL='https://assets.kalshi.com/contract_terms/FOOTBALLENTITYSTAT.pdf';
// Verified public regulatory document: includes regulation+OT, participation and
// discretionary fair-price exceptions. A changed document requires review.
export const FOOTBALL_TERMS_SHA256='667ec1a9b87681a4f26225ad2bbcd0a90b7032a6843a48a493ba5d77669e99fe';
export const KALSHI_FEE_SOURCE='https://kalshi.com/docs/kalshi-fee-schedule.pdf';
const MONTHS=['JAN','FEB','MAR','APR','MAY','JUN','JUL','AUG','SEP','OCT','NOV','DEC'];
const TEAM_LABELS:Record<string,string>={ARI:'Arizona',ATL:'Atlanta',BAL:'Baltimore',BUF:'Buffalo',CAR:'Carolina',CHI:'Chicago',CIN:'Cincinnati',CLE:'Cleveland',DAL:'Dallas',DEN:'Denver',DET:'Detroit',GB:'Green Bay',HOU:'Houston',IND:'Indianapolis',JAX:'Jacksonville',KC:'Kansas City',LA:'Los Angeles R',LAC:'Los Angeles C',LV:'Las Vegas',MIA:'Miami',MIN:'Minnesota',NE:'New England',NO:'New Orleans',NYG:'New York G',NYJ:'New York J',PHI:'Philadelphia',PIT:'Pittsburgh',SEA:'Seattle',SF:'San Francisco',TB:'Tampa Bay',TEN:'Tennessee',WAS:'Washington'};
const UUID=/^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/i;
const text=(value:unknown)=>typeof value==='string'?value.replace(/\s+/g,' ').trim():'';
export const canonicalPropName=(value:string)=>value.normalize('NFKC').replace(/[’‘]/g,"'").replace(/\s+/g,' ').trim().toLowerCase();
export const canonicalPropTeam=(value:string)=>({LAR:'LA',JAC:'JAX',WSH:'WAS'} as Record<string,string>)[value]??value;
const code=(team:string)=>({LA:'LAR',JAX:'JAC'} as Record<string,string>)[canonicalPropTeam(team)]??canonicalPropTeam(team);
function amount(value:unknown,max?:number):Decimal|null{
 if(typeof value!=='string'||!/^\d{1,16}(?:\.\d{1,8})?$/.test(value))return null;
 const result=new Decimal(value);return result.isFinite()&&result.gte(0)&&(max===undefined||result.lte(max))?result:null;
}
function cents(value:unknown,allowBoundary=false):string|null{const result=amount(value,1);return result&&(allowBoundary||result.gt(0)&&result.lt(1))?result.mul(100).toString():null;}
function eventDate(game:PublicGame){
 if(!Number.isFinite(Date.parse(game.startTime)))return null;
 const d=Object.fromEntries(new Intl.DateTimeFormat('en-US',{timeZone:'America/New_York',year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(new Date(game.startTime)).map(p=>[p.type,p.value]));
 return{year:d.year,month:Number(d.month),day:Number(d.day)};
}
export function kalshiPropEventTicker(series:string,game:PublicGame){const d=eventDate(game);return d&&TEAM_LABELS[canonicalPropTeam(game.home.id)]&&TEAM_LABELS[canonicalPropTeam(game.away.id)]?`${series}-${d.year.slice(-2)}${MONTHS[d.month-1]}${String(d.day).padStart(2,'0')}${code(game.away.id)}${code(game.home.id)}`:null;}
export function unverifiedPropFees(observedAt:string,type:string|null=null,multiplier:string|null=null):PropFees{return{calculationStatus:'unverified',entryFeeCents:null,winFeeCents:null,rounding:null,type,multiplier,sourceUrl:KALSHI_FEE_SOURCE,reason:'Exact entry fees depend on effective event overrides, clearing/broker terms, quantity, account precision, fills and per-order rounding rebates. Missing costs are not assumed to be zero.',observedAt};}
export type StructuredTarget={id:string;name:string;type:string;details?:Record<string,any>};
export type NormalizationResult={contract:PropMarketContract|null;reason:string|null};

export function normalizeKalshiPropMarket(game:PublicGame,market:any,series:any,targets:Map<string,StructuredTarget>,observedAt:string,sourceUrl:string,termsHash:string|null):NormalizationResult{
 const reject=(reason:string):NormalizationResult=>({contract:null,reason});
 const supported=KALSHI_PROP_SERIES.find(s=>s.ticker===series?.ticker),d=eventDate(game);
 if(!supported||!d)return reject('Unsupported player-stat series or game identity.');
 const event=kalshiPropEventTicker(supported.ticker,game);
 if(market?.event_ticker!==event||market.market_type!=='binary'||!['active','open'].includes(market.status)||market.primary_participant_key!=='football_player')return reject('Market event, type, status or participant identity did not match the trusted NFL game.');
 if(market.is_provisional===true||market.result) return reject('The exchange marked this contract provisional or already resolved.');
 if(amount(market.notional_value_dollars,1)?.eq(1)!==true||market.strike_type!=='greater')return reject('Unsupported payout or threshold operator.');
 const playerId=market.custom_strike?.football_player,teamId=market.custom_strike?.football_team;
 if(typeof playerId!=='string'||!UUID.test(playerId)||typeof teamId!=='string'||!UUID.test(teamId))return reject('Missing structured player/team identifiers.');
 const player=targets.get(playerId),team=targets.get(teamId);
 if(player?.type!=='football_player'||team?.type!=='football_team'||player.details?.league!=='NFL'||team.details?.league!=='NFL'||player.details.team_id!==teamId)return reject('The public structured player/team mapping could not be independently verified.');
 const teamCode=canonicalPropTeam(String(team.details.abbreviation??''));
 if(![canonicalPropTeam(game.home.id),canonicalPropTeam(game.away.id)].includes(teamCode)||!player.name||player.name.length>120)return reject('Player team is not a participant in this scheduled game.');
 const primary=text(market.rules_primary),secondary=text(market.rules_secondary);
 const match=primary.match(/^If (.+?) (?:records|scores at least) (\d{1,4})\+ (.+?) in the (.+?) vs (.+?) (?:Pro|Professional) Football game originally scheduled for ([A-Za-z]{3}) (\d{1,2}), (\d{4}), then the market resolves to Yes\.$/i);
 if(!match||canonicalPropName(match[1])!==canonicalPropName(player.name)||match[3].toLowerCase()!==supported.wording||match[4]!==TEAM_LABELS[canonicalPropTeam(game.away.id)]||match[5]!==TEAM_LABELS[canonicalPropTeam(game.home.id)]||match[6].toUpperCase()!==MONTHS[d.month-1]||Number(match[7])!==d.day||match[8]!==d.year)return reject('The exact player, statistic, matchup or date in the settlement rule did not match.');
 const threshold=Number(match[2]);
 if(!Number.isFinite(market.floor_strike)||market.floor_strike!==threshold-.5||market.cap_strike!=null||text(market.yes_sub_title)!==`${player.name}: ${threshold}+`||text(market.no_sub_title)!==text(market.yes_sub_title))return reject('The displayed threshold disagrees with the numeric strike or outcome labels.');
 const participantAbbreviation=text(player.details.abbreviation);
 if(!participantAbbreviation||market.ticker!==`${event}-${code(teamCode)}${participantAbbreviation}-${threshold}`)return reject('Contract identifier disagrees with the structured player, team or threshold.');
 const participation=`If ${player.name} is active but never takes a snap, the market settles to the fair market price before game start.`;
 const counting=`Once ${player.name} takes at least one snap, even if nullified by penalty, the market settles based on ${supported.stat==='touchdowns'?'touchdowns scored':supported.wording+' recorded'}.`;
 if(!secondary.includes(participation)||!secondary.includes(counting)||!/The following market refers to /.test(secondary))return reject('Player participation or statistical settlement rules are unsupported.');
 const yesAsk=cents(market.yes_ask_dollars),noAsk=cents(market.no_ask_dollars),yesBid=cents(market.yes_bid_dollars),noBid=cents(market.no_bid_dollars);
 if(yesAsk!==null&&yesBid!==null&&new Decimal(yesBid).gt(yesAsk)||noAsk!==null&&noBid!==null&&new Decimal(noBid).gt(noAsk))return reject('Crossed bid/ask quotes were withheld.');
 if(noAsk!==null&&yesBid!==null&&!new Decimal(noAsk).add(yesBid).eq(100)||noBid!==null&&yesAsk!==null&&!new Decimal(noBid).add(yesAsk).eq(100))return reject('Binary opposite-side prices did not reconcile.');
 const yesAskSize=amount(market.yes_ask_size_fp),yesBidSize=amount(market.yes_bid_size_fp);
 const validYesAsk=yesAsk!==null&&yesAskSize?.gt(0)?yesAsk:null,validNoAsk=noAsk!==null&&yesBidSize?.gt(0)&&yesBid!==null?noAsk:null;
 if(validYesAsk===null&&validNoAsk===null)return reject('No positive-size observed offer could be verified on either side.');
 const observedMs=Date.parse(observedAt),now=Date.now(),openMs=Date.parse(market.open_time),closeMs=Date.parse(market.close_time);
 const current=Number.isFinite(observedMs)&&observedMs<=now+60000&&now-observedMs<=120000&&Date.parse(game.startTime)>now&&Number.isFinite(openMs)&&openMs<=now&&Number.isFinite(closeMs)&&closeMs>now;
 const rulesVerified=series.contract_terms_url===FOOTBALL_TERMS_URL&&termsHash===FOOTBALL_TERMS_SHA256;
 const modelCompatible=rulesVerified&&supported.stat!=='touchdowns';
 const issues:string[]=[];if(!current)issues.push('The observed market snapshot is stale, not yet open or the game has started.');if(!rulesVerified)issues.push('The current regulatory terms document needs verification.');if(supported.stat==='touchdowns')issues.push('The simulator attributes rushing/receiving touchdowns only; defensive and return-touchdown outcomes are not fully covered.');
 issues.push('Probabilities are conditional on participation and normal game completion. Discretionary fair-price exceptions are not modeled.','Exact transaction fees and guaranteed execution are unavailable.');
 const volume=amount(market.volume_fp),lastPrice=volume?.gt(0)?cents(market.last_price_dollars,true):null;
 const feeType=typeof series.fee_type==='string'?series.fee_type:null,feeMultiplier=typeof series.fee_multiplier==='number'&&Number.isFinite(series.fee_multiplier)&&series.fee_multiplier>=0?String(series.fee_multiplier):null;
 return{contract:{id:`Kalshi:${market.ticker}`,contractId:market.ticker,eventId:event!,gameId:game.id,eventStart:game.startTime,provider:'Kalshi',sourceKind:'public_exchange',playerId:null,playerName:player.name,providerPlayerId:playerId,team:teamCode,opponent:canonicalPropTeam(game.home.id)===teamCode?canonicalPropTeam(game.away.id):canonicalPropTeam(game.home.id),position:typeof player.details.position==='string'?player.details.position:null,stat:supported.stat,category:supported.category,threshold,operator:'gte',title:text(market.title)||`${player.name}: ${threshold}+ ${supported.wording}`,sourceThreshold:{floorStrike:market.floor_strike,capStrike:null,strikeType:'greater'},yesAskCents:validYesAsk,noAskCents:validNoAsk,yesBidCents:yesBid,noBidCents:noBid,lastTradedPriceCents:lastPrice,quotedAt:null,observedAt,sourceUpdatedAt:typeof market.updated_time==='string'?market.updated_time:null,quoteTimestampMeaning:'Observed public BBO at collection. Market updated_time is metadata, not a verified quote-change timestamp; no authenticated execution is claimed.',liquidity:{yesAskContracts:validYesAsk?yesAskSize!.toString():null,yesBidContracts:yesBidSize?.gt(0)?yesBidSize.toString():null,noAskContracts:validNoAsk?yesBidSize!.toString():null,noBidContracts:noBid&&yesAskSize?.gt(0)?yesAskSize.toString():null,openInterest:amount(market.open_interest_fp)?.toString()??null,volume:volume?.toString()??null},fees:unverifiedPropFees(observedAt,feeType,feeMultiplier),rules:primary+'\n\n'+secondary,rulesUrl:FOOTBALL_TERMS_URL,rulesHash:sha({primary,secondary,termsHash}),sourceUrl,draftKingsEquivalent:false,mapping:{status:'unmapped',method:'provider_structured_identity_pending_NFL_roster',reason:'A matching current NFL roster is required before assigning a GSIS player ID.'},verification:{current,quoteVerified:current,executionVerified:false,issues},settlement:{modelCompatible,rulesVerified,fullGame:true,overtimeIncluded:rulesVerified,nonParticipationPolicy:'fair_price',probabilityBasis:'conditional_on_participation_and_normal_completion',unconditionalValuationSupported:false,statCoverage:supported.stat==='touchdowns'?'all_player_touchdowns_required; model_offensive_only':'specified_official_full_game_stat',reason:modelCompatible?'Normal-participation, full-game threshold can be evaluated; fair-price exceptions and availability mixtures remain unvalued.':'Statistical coverage or current regulatory terms do not support this contract.',termsVersion:termsHash}},reason:null};
}

export function resolvePlayerPropIdentity(contract:PropMarketContract,catalog:PropPlayerIdentity[]):PropMarketContract{
 if(isGameMarket(contract.stat))return contract;
 const names=new Set([canonicalPropName(contract.playerName)]),team=canonicalPropTeam(contract.team);
 const matches=catalog.filter(player=>canonicalPropTeam(player.team)===team&&[player.name,...player.aliases??[]].some(name=>names.has(canonicalPropName(name))));
 if(matches.length!==1||!/^00-\d{7}$/.test(matches[0]?.id??''))return{...contract,playerId:null,mapping:{status:matches.length>1?'conflict':'unmapped',method:'exact_NFL_roster_name_and_team',reason:matches.length>1?'More than one current roster identity matches; no player ID was guessed.':'No unique GSIS identity matches the exact current roster name and team.'}};
 const player=matches[0];return{...contract,playerId:player.id,position:player.position??contract.position,mapping:{status:'verified',method:'provider_structured_identity_and_exact_NFL_roster_name_team',reason:null,...player.rosterWeek?{rosterWeek:player.rosterWeek}:{}}};
}

/** Re-evaluate persisted observations at read time. A capture-time boolean can
 * never make an old quote or a manual snapshot look currently available. */
export function isCurrentPropQuote(contract:PropMarketContract,time:number|Date=Date.now()){
 const now=time instanceof Date?time.getTime():time,at=Date.parse(contract.quotedAt??contract.observedAt);
 return contract.sourceKind!=='manual_verified'&&contract.verification.quoteVerified&&Number.isFinite(at)&&at<=now+60000&&now-at<=120000&&Date.parse(contract.eventStart)>now;
}
export function recheckPropMarketFreshness(contract:PropMarketContract,now:number|Date=Date.now()):PropMarketContract{
 const current=isCurrentPropQuote(contract,now);return{...contract,verification:{...contract.verification,current,...current?{}:{issues:[...new Set([...contract.verification.issues,'This saved quote is historical or its current availability could not be verified.'])]}}};
}
