import {isIP} from 'node:net';
import {performance} from 'node:perf_hooks';
import {z} from 'zod';
import {source,sha} from '../public-nfl/sources';
import type {ResearchSource,PublicGame} from '../public-nfl/types';
import type {PropMarketContract,PropMarketDiscovery,PropPlayerIdentity,PropProviderOptions,PropProviderStatus} from './market-types';
import {PROP_STATS,isGameMarket} from './market-types';
import {KALSHI_GAME_SERIES,normalizeKalshiGameMarket,normalizeAuthorizedGameContract} from './game-markets';
import {KALSHI_PROP_SERIES,FOOTBALL_TERMS_URL,FOOTBALL_TERMS_SHA256,KALSHI_FEE_SOURCE,kalshiPropEventTicker,normalizeKalshiPropMarket,resolvePlayerPropIdentity,canonicalPropTeam,canonicalPropName,unverifiedPropFees,type StructuredTarget} from './normalize';

export const KALSHI_PROP_API='https://external-api.kalshi.com/trade-api/v2';
export const KALSHI_PROP_DOCS='https://docs.kalshi.com/getting_started/quick_start_market_data';
const MAX_SOURCE_BYTES=5_000_000,MAX_PAGES=4,CACHE_MS=60000;
let cached:{key:string;until:number;value:PropMarketDiscovery}|undefined;
const pending=new Map<string,Promise<PropMarketDiscovery>>();
const milliseconds=(value:string)=>Date.parse(value);
const cleanUrl=(url:URL)=>url.origin+url.pathname;
export function draftKingsFeedConfigured(){return Boolean(process.env.GRIDIRON_DK_PREDICTIONS_FEED_URL&&process.env.GRIDIRON_DK_PREDICTIONS_FEED_AUTHORIZED==='1');}
async function readBytes(url:string,transport:typeof fetch,headers:Record<string,string>={},maximum=MAX_SOURCE_BYTES){
 const response=await transport(url,{method:'GET',headers:{Accept:'application/json,application/pdf,*/*',...headers},cache:'no-store',redirect:'error',signal:AbortSignal.timeout(10000)});
 if(!response.ok)throw new Error('The authorized market source could not be verified.');
 if(Number(response.headers.get('content-length')||0)>maximum)throw new Error('Market source exceeds its safe ingestion bound.');
 const reader=response.body?.getReader();if(!reader)throw new Error('Market source returned no readable body.');
 const chunks:Uint8Array[]=[];let size=0;
 for(;;){const {done,value}=await reader.read();if(done)break;size+=value.byteLength;if(size>maximum){await reader.cancel();throw new Error('Market source exceeds its safe ingestion bound.');}chunks.push(value);}
 return Buffer.concat(chunks);
}
async function readJson(url:string,transport:typeof fetch,headers:Record<string,string>={},maximum=MAX_SOURCE_BYTES):Promise<any>{return JSON.parse((await readBytes(url,transport,headers,maximum)).toString('utf8'));}
function pacedPublicTransport(transport:typeof fetch,deadline:number):typeof fetch{
 let nextRequestAt=performance.now();
 return async(input,options)=>{
  for(let attempt=0;attempt<3;attempt++){
   if(performance.now()>deadline)throw Error('The public source refresh reached its bounded research window.');
   const at=Math.max(performance.now(),nextRequestAt);nextRequestAt=at+150;
   if(at>performance.now())await new Promise(resolve=>setTimeout(resolve,at-performance.now()));
   if(performance.now()>deadline)throw Error('The public source refresh reached its bounded research window.');
   const response=await transport(input,options);
   if(response.status!==429||attempt===2)return response;
   await response.body?.cancel();await new Promise(resolve=>setTimeout(resolve,1000*2**attempt));
  }
  throw Error('The public source is temporarily rate limited.');
 };
}
async function concurrent<T,R>(values:T[],count:number,work:(value:T)=>Promise<R>):Promise<PromiseSettledResult<R>[]>{
 const results=new Array<PromiseSettledResult<R>>(values.length);let next=0;
 await Promise.all(Array.from({length:Math.min(count,values.length)},async()=>{for(;;){const index=next++;if(index>=values.length)return;try{results[index]={status:'fulfilled',value:await work(values[index])};}catch(reason){results[index]={status:'rejected',reason};}}}));return results;
}
const idString=z.string().min(1).max(200),money=z.string().regex(/^\d{1,6}(?:\.\d{1,8})?$/),price=money.refine(value=>Number(value)>0&&Number(value)<100),nullablePrice=price.nullable().optional();
const https=z.string().url().refine(value=>{const u=new URL(value);return u.protocol==='https:'&&!u.username&&!u.password&&![...u.searchParams.keys()].some(key=>/token|signature|key|secret|password|authorization/i.test(key));});
export const authorizedPropContractSchema=z.object({
 provider:z.literal('DraftKings Predictions'),marketType:z.literal('event_contract'),contractId:idString,eventId:idString,gameId:idString,
 playerId:z.string().regex(/^00-\d{7}$/),playerName:z.string().min(2).max(120),team:z.string().min(2).max(3),stat:z.enum(PROP_STATS),threshold:z.number().finite(),operator:z.enum(['gt','gte','lt','lte','eq']),eventStart:z.string().datetime({offset:true}),
 yesAskCents:nullablePrice,noAskCents:nullablePrice,yesBidCents:nullablePrice,noBidCents:nullablePrice,lastTradedPriceCents:money.nullable().optional(),
 quotedAt:z.string().datetime({offset:true}),status:z.enum(['open','closed','suspended']),title:z.string().min(3).max(500),rules:z.string().min(30).max(10000),rulesUrl:https,sourceUrl:https,
 fees:z.object({entryFeeCents:money,winFeeCents:money,rounding:z.enum(['none','up_to_cent','collateral_total_up_to_cent']),sourceUrl:https,verified:z.literal(true)}).nullable().optional(),
 liquidity:z.object({yesAskContracts:money.nullable().optional(),yesBidContracts:money.nullable().optional(),noAskContracts:money.nullable().optional(),noBidContracts:money.nullable().optional()}).optional(),
 displayedYesPercent:money.refine(v=>Number(v)<=100).nullable().optional(),displayedNoPercent:money.refine(v=>Number(v)<=100).nullable().optional(),
 settlement:z.object({stat:z.enum(PROP_STATS),threshold:z.number().finite(),operator:z.enum(['gt','gte','lt','lte','eq']),fullGame:z.boolean(),overtimeIncluded:z.boolean(),nonParticipationPolicy:z.enum(['fair_price','void','stat_zero','unknown']),verified:z.literal(true)}),
});

/** This is an explicit integration contract for a licensed feed configured by
 * the operator, not a claim that DraftKings publishes this URL or API schema. */
export function normalizeAuthorizedPropContract(input:unknown,games:PublicGame[],catalog:PropPlayerIdentity[],observedAt:string,sourceKind:'authorized_feed'|'manual_verified'='authorized_feed'):PropMarketContract{
 if(input&&typeof input==='object'&&isGameMarket(String((input as any).stat)))return normalizeAuthorizedGameContract(input,games,observedAt,sourceKind);
 const q=authorizedPropContractSchema.parse(input),game=games.find(game=>game.id===q.gameId),now=milliseconds(observedAt);
 const credential=process.env.GRIDIRON_DK_PREDICTIONS_FEED_TOKEN;
 if(credential&&JSON.stringify(q).includes(credential))throw Error('The source echoed a server credential; that contract was withheld.');
 if(!game||milliseconds(game.startTime)!==milliseconds(q.eventStart)||![canonicalPropTeam(game.home.id),canonicalPropTeam(game.away.id)].includes(canonicalPropTeam(q.team)))throw Error('Contract matchup, kickoff or team disagrees with the verified schedule.');
 if(q.settlement.stat!==q.stat||q.settlement.threshold!==q.threshold||q.settlement.operator!==q.operator)throw Error('Contract threshold or statistic disagrees with its exact settlement definition.');
 if(milliseconds(q.quotedAt)>now+60000)throw Error('A contract quote cannot be captured in the future.');
 if(q.yesBidCents&&q.yesAskCents&&Number(q.yesBidCents)>Number(q.yesAskCents)||q.noBidCents&&q.noAskCents&&Number(q.noBidCents)>Number(q.noAskCents))throw Error('Crossed contract quotes were withheld.');
 if(q.lastTradedPriceCents&&Number(q.lastTradedPriceCents)>100||q.fees&&Number(q.fees.winFeeCents)>=100)throw Error('Price or fee terms exceed the binary payout.');
 const matched=catalog.filter(p=>p.id===q.playerId&&canonicalPropTeam(p.team)===canonicalPropTeam(q.team)&&[p.name,...p.aliases??[]].some(n=>canonicalPropName(n)===canonicalPropName(q.playerName)));
 if(catalog.length&&matched.length!==1)throw Error('The exact GSIS player, roster name and team mapping could not be verified.');
 const current=sourceKind!=='manual_verified'&&q.status==='open'&&Boolean(q.yesAskCents||q.noAskCents||q.displayedYesPercent!==undefined&&q.displayedYesPercent!==null||q.displayedNoPercent!==undefined&&q.displayedNoPercent!==null)&&now-milliseconds(q.quotedAt)<=120000&&milliseconds(game.startTime)>now;
 const covered=q.stat!=='touchdowns',compatible=q.settlement.fullGame&&q.settlement.overtimeIncluded&&q.settlement.nonParticipationPolicy!=='unknown'&&covered;
 const issues:string[]=[];if(sourceKind==='manual_verified')issues.push('User-verified manual snapshot; current live availability and execution are not independently verified.');if(!current)issues.push('This is not a verified current executable contract snapshot.');if(!q.fees)issues.push('Transaction fees are unavailable; no zero-cost assumption is made.');if(!compatible)issues.push('The complete-game model does not cover every stated settlement condition.');
 issues.push('Model probabilities are conditional on player participation and normal game completion; unconditional valuation needs supported availability and exception scenarios.');
 const team=canonicalPropTeam(q.team),fees=q.fees?{calculationStatus:'verified_explicit' as const,entryFeeCents:q.fees.entryFeeCents,winFeeCents:q.fees.winFeeCents,rounding:q.fees.rounding,type:'explicit_per_contract',multiplier:null,sourceUrl:q.fees.sourceUrl,reason:'Explicit fee terms supplied by the authorized source or user-verified snapshot; no broker or execution terms are inferred.',observedAt}:unverifiedPropFees(observedAt);
 const contract:PropMarketContract={id:`${sourceKind==='manual_verified'?'Manual':'DraftKings Predictions'}:${q.contractId}`,contractId:q.contractId,eventId:q.eventId,gameId:game.id,eventStart:game.startTime,provider:'DraftKings Predictions',sourceKind,playerId:matched.length?q.playerId:null,playerName:q.playerName,providerPlayerId:q.playerId,team,opponent:canonicalPropTeam(game.home.id)===team?canonicalPropTeam(game.away.id):canonicalPropTeam(game.home.id),position:matched[0]?.position??null,stat:q.stat,category:KALSHI_PROP_SERIES.find(s=>s.stat===q.stat)?.category??q.stat,threshold:q.threshold,operator:q.operator,title:q.title,sourceThreshold:{floorStrike:null,capStrike:null,strikeType:q.operator},yesAskCents:q.yesAskCents??null,noAskCents:q.noAskCents??null,yesBidCents:q.yesBidCents??null,noBidCents:q.noBidCents??null,lastTradedPriceCents:q.lastTradedPriceCents??null,quotedAt:q.quotedAt,observedAt,sourceUpdatedAt:null,quoteTimestampMeaning:sourceKind==='manual_verified'?'User-verified historical quote capture; not a verified live execution.':'Source-supplied quote timestamp from the explicitly authorized event-contract feed.',liquidity:{yesAskContracts:q.liquidity?.yesAskContracts??null,yesBidContracts:q.liquidity?.yesBidContracts??null,noAskContracts:q.liquidity?.noAskContracts??null,noBidContracts:q.liquidity?.noBidContracts??null,openInterest:null,volume:null},fees,rules:q.rules,rulesUrl:q.rulesUrl,rulesHash:sha({rules:q.rules,definition:q.settlement}),sourceUrl:q.sourceUrl,draftKingsEquivalent:sourceKind==='authorized_feed',mapping:{status:matched.length?'verified':'unmapped',method:'exact_GSIS_name_and_current_roster_team',reason:matched.length?null:'Waiting for the current NFL roster identity catalog.'},verification:{current,quoteVerified:sourceKind==='manual_verified'||current,executionVerified:false,issues},settlement:{modelCompatible:compatible,rulesVerified:true,fullGame:q.settlement.fullGame,overtimeIncluded:q.settlement.overtimeIncluded,nonParticipationPolicy:q.settlement.nonParticipationPolicy,probabilityBasis:'conditional_on_participation_and_normal_completion',unconditionalValuationSupported:false,statCoverage:covered?'specified_full_game_stat':'all_touchdowns_require_unmodeled_return_and_defensive_coverage',reason:'Structured settlement definition must agree exactly; availability mixtures and exceptional settlement cases remain separate evidence requirements.',termsVersion:sha(q.rules)}};
 return{...contract,subject:{kind:'player',teamId:contract.team},displayedYesPercent:q.displayedYesPercent??null,displayedNoPercent:q.displayedNoPercent??null};
}
export function normalizeVerifiedManualProp(input:unknown,games:PublicGame[],catalog:PropPlayerIdentity[],now=new Date()){return normalizeAuthorizedPropContract(input,games,catalog,now.toISOString(),'manual_verified');}

function configuredFeedUrl():URL|null{
 const raw=process.env.GRIDIRON_DK_PREDICTIONS_FEED_URL;if(!raw)return null;
 const url=new URL(raw),host=url.hostname.toLowerCase();
 if(url.protocol!=='https:'||url.username||url.password||url.port&&url.port!=='443'||isIP(host)||host==='localhost'||host.endsWith('.localhost')||host.endsWith('.local')||!host.includes('.')||[...url.searchParams.keys()].some(key=>/token|key|secret|password/i.test(key)))throw Error('The authorized feed URL must use a public HTTPS host and server-side header credentials.');
 return url;
}
async function discoverDraftKings(games:PublicGame[],transport:typeof fetch,observedAt:string,includeGames=false):Promise<{contracts:PropMarketContract[];status:PropProviderStatus;sources:ResearchSource[];rejected:PropMarketDiscovery['rejected'];complete:boolean}>{
 const info:Omit<PropProviderStatus,'status'|'message'>={provider:'DraftKings Predictions',checkedAt:observedAt,contracts:0,sourceUrl:'https://predictions.draftkings.com/en',categories:[]};
 if(!draftKingsFeedConfigured())return{contracts:[],status:{...info,status:'unavailable',message:'An authorized DraftKings Predictions NFL event-contract feed is not connected. DraftKings Sportsbook odds and separately selected exchange alternatives are not DraftKings Predictions prices.'},sources:[],rejected:[],complete:true};
 const contracts:PropMarketContract[]=[],rejected:PropMarketDiscovery['rejected']=[];let complete=true;
 try{
  const base=configuredFeedUrl()!,headers:Record<string,string>={};if(process.env.GRIDIRON_DK_PREDICTIONS_FEED_TOKEN)headers.Authorization='Bearer '+process.env.GRIDIRON_DK_PREDICTIONS_FEED_TOKEN;
  let cursor:string|undefined;
  for(let page=0;page<MAX_PAGES;page++){
   const url=new URL(base);if(cursor)url.searchParams.set('cursor',cursor);
   const body=await readJson(url.href,transport,headers);
   if(!['gridiron-player-prop-contracts-v1','gridiron-nfl-event-contracts-v1'].includes(body?.schema)||body.provider!=='DraftKings Predictions'||!Array.isArray(body.contracts)||body.contracts.length>1000)throw Error('Unsupported authorized feed schema.');
   for(const value of body.contracts){if(!includeGames&&isGameMarket(String(value?.stat)))continue;try{contracts.push(normalizeAuthorizedPropContract(value,games,[],observedAt));}catch{rejected.push({contractId:typeof value?.contractId==='string'?value.contractId.slice(0,200):'unverified',reason:'The authorized source returned an unsupported identity, threshold, price or settlement definition.'});}}
   if(body.nextCursor===null||body.nextCursor===undefined||body.nextCursor===''){cursor=undefined;break;}
   if(typeof body.nextCursor!=='string'||body.nextCursor.length>500||body.nextCursor===cursor)throw Error('Unsupported market pagination.');cursor=body.nextCursor;if(page===MAX_PAGES-1)complete=false;
  }
  const unique=[...new Map(contracts.map(c=>[c.id,c])).values()];return{contracts:unique,status:{...info,status:unique.length&&complete&&unique.every(c=>c.settlement.modelCompatible&&c.verification.current)?'available':'partial',contracts:unique.length,categories:[...new Set(unique.map(c=>c.category))],message:unique.length?'Observed authorized DraftKings Predictions event-contract snapshots. Prices, fees and exceptional settlement coverage remain individually audited.':'No supported current NFL player contracts were verified in the authorized source.'},sources:[source('dk-authorized-player-props','Authorized DraftKings Predictions contract feed',cleanUrl(base),observedAt,complete?'available':'partial','Operator-authorized event-contract integration; not a public DraftKings API or sportsbook substitution.')],rejected,complete};
 }catch{return{contracts:[],status:{...info,status:'unavailable',message:'The authorized DraftKings contract feed could not be verified. No fallback price or unsupported market definition was invented.'},sources:[],rejected,complete:false};}
}

async function discoverKalshi(games:PublicGame[],transport:typeof fetch,observedAt:string,includeGames=false){
 const publicTransport=pacedPublicTransport(transport,performance.now()+75000);
 const batches=[...KALSHI_PROP_SERIES,...includeGames?KALSHI_GAME_SERIES:[]].map(series=>({series,games,tickers:games.map(game=>kalshiPropEventTicker(series.ticker,game)).filter((v):v is string=>Boolean(v))}));
 // The documented events endpoint includes nested full market definitions.
 // Ten events per page keeps even receiving-yard responses below the byte cap.
 // This avoids hundreds of per-event requests and respects public rate limits.
 const sourceList:ResearchSource[]=[source('kalshi-public-player-prop-docs','Kalshi public market-data API documentation reference',KALSHI_PROP_DOCS,observedAt,'partial','Documentation reference, not a statistical data retrieval in this scan. Fixed read-only public endpoints are used; no orders or DraftKings equivalence is implied.')];
 let complete=true;const rawMarkets:any[]=[],seriesMap=new Map<string,any>(),gameByEvent=new Map<string,PublicGame>();for(const batch of batches)for(const game of batch.games){const ticker=kalshiPropEventTicker(batch.series.ticker,game);if(ticker)gameByEvent.set(ticker,game);}
 const jobs=await concurrent(batches,4,async batch=>{
  const values:any[]=[];let cursor:string|undefined;
  for(let page=0;page<MAX_PAGES;page++){
   const url=new URL(KALSHI_PROP_API+'/events');url.searchParams.set('series_ticker',batch.series.ticker);url.searchParams.set('with_nested_markets','true');url.searchParams.set('status','open');url.searchParams.set('limit','10');if(cursor)url.searchParams.set('cursor',cursor);
   const body=await readJson(url.href,publicTransport);
   if(!Array.isArray(body.events)||body.events.length>10)throw Error('Unexpected public event response.');
   // An upstream filter bug cannot broaden a scan to unrelated events. Only
   // trusted schedule-matched events reach identity checks or model evaluation.
   for(const event of body.events){if(!batch.tickers.includes(event?.event_ticker))continue;if(event.series_ticker!==batch.series.ticker||!Array.isArray(event.markets)||event.markets.length>1000)throw Error('Incomplete player-contract event definitions.');values.push(...event.markets.filter((m:any)=>m?.event_ticker===event.event_ticker));}
   if(!body.cursor){cursor=undefined;break;}if(typeof body.cursor!=='string'||body.cursor.length>1000||body.cursor===cursor)throw Error('Unstable public market pagination.');cursor=body.cursor;if(page===MAX_PAGES-1)complete=false;
  }
  sourceList.push(source('kalshi-player-props-'+batch.series.ticker,'Kalshi '+batch.series.category+' contract quotes',KALSHI_PROP_API+'/events?series_ticker='+batch.series.ticker+'&with_nested_markets=true',observedAt,'available','Observed BBO from nested market definitions; opposite-side liquidity follows the documented binary YES/NO complement. Updated metadata time is not used as quote freshness.'));
  return values;
 });
 for(let index=0;index<jobs.length;index++){const item=jobs[index];if(item.status==='fulfilled')rawMarkets.push(...item.value);else{complete=false;const batch=batches[index];sourceList.push(source('kalshi-player-props-failed-'+index,'Kalshi '+batch.series.category+' contract quotes',KALSHI_PROP_API+'/events?series_ticker='+batch.series.ticker,observedAt,'unavailable','This category quote refresh failed or was rate limited. Previously observed prices are not declared current.'));}}
 const seriesNeeded=[...new Set(rawMarkets.map(m=>String(m.event_ticker).split('-')[0]))];
 const metadata=await concurrent(seriesNeeded,4,async ticker=>{const value=await readJson(KALSHI_PROP_API+'/series/'+encodeURIComponent(ticker),publicTransport,{},500000);if(value?.series?.ticker!==ticker)throw Error('Series identity mismatch.');return value.series;});
 for(const item of metadata)if(item.status==='fulfilled')seriesMap.set(item.value.ticker,item.value);else complete=false;
 let termsHash:string|null=null;try{termsHash=sha(await readBytes(FOOTBALL_TERMS_URL,transport,{},1_000_000));if(termsHash!==FOOTBALL_TERMS_SHA256)complete=false;}catch{complete=false;}
 const gameTerms=new Map<string,string|null>();if(includeGames){const terms=await concurrent([...new Set(KALSHI_GAME_SERIES.map(s=>s.terms))].filter(v=>v!=='FOOTBALLENTITYSTAT'),3,async name=>({name,hash:sha(await readBytes(`https://assets.kalshi.com/contract_terms/${name}.pdf`,transport,{},1_000_000))}));for(const item of terms)if(item.status==='fulfilled'){gameTerms.set(item.value.name,item.value.hash);sourceList.push(source('kalshi-game-terms-'+item.value.name,'Kalshi full-game settlement terms',`https://assets.kalshi.com/contract_terms/${item.value.name}.pdf`,observedAt,'partial','Public full-game terms include overtime, exceptional payouts and cancellation conditions; exact current bytes are retained by hash.',item.value.hash));}else complete=false;gameTerms.set('FOOTBALLENTITYSTAT',termsHash);}
 let feeDocumentHash:string|null=null;try{const bytes=await readBytes(KALSHI_FEE_SOURCE,transport,{},1_000_000);if(bytes.subarray(0,4).toString()==='%PDF')feeDocumentHash=sha(bytes);}catch{/* Missing fee evidence cannot become zero fees. */}
 sourceList.push(source('kalshi-player-prop-regulatory-terms','Kalshi full-game player-stat settlement terms',FOOTBALL_TERMS_URL,observedAt,termsHash===FOOTBALL_TERMS_SHA256?'available':'unavailable','Participation and exceptional fair-price rules are retained. A changed document requires re-verification.',termsHash??undefined),source('kalshi-player-prop-fees','Kalshi current fee schedule',KALSHI_FEE_SOURCE,observedAt,feeDocumentHash?'partial':'unavailable','Exact account/broker fees and effective override/rounding terms are not established; after-cost valuation is withheld.',feeDocumentHash??undefined));
 const identifiers=[...new Set(rawMarkets.flatMap(m=>[m.custom_strike?.football_player,m.custom_strike?.football_team]).filter(v=>typeof v==='string'&&/^[a-f0-9-]{36}$/i.test(v)))],targets=new Map<string,StructuredTarget>();
 const chunks=Array.from({length:Math.ceil(identifiers.length/100)},(_,index)=>identifiers.slice(index*100,index*100+100));
 const targetResponses=await concurrent(chunks,3,async ids=>{const url=new URL(KALSHI_PROP_API+'/structured_targets');url.searchParams.set('page_size','2000');for(const id of ids)url.searchParams.append('ids',id);const body=await readJson(url.href,publicTransport,{},2_000_000);if(!Array.isArray(body.structured_targets)||body.cursor)throw Error('Incomplete structured target identities.');return body.structured_targets.filter((target:any)=>ids.includes(target?.id));});
 for(const response of targetResponses)if(response.status==='fulfilled'){for(const target of response.value)targets.set(target.id,target);}else complete=false;
 if(chunks.length)sourceList.push(source('kalshi-player-prop-identities','Kalshi structured player and team identities',KALSHI_PROP_API+'/structured_targets',observedAt,targetResponses.every(v=>v.status==='fulfilled')?'available':'partial','Only entity identity is used. Vendor player projections, roster status and other statistics are not imported as model evidence.'));
 const contracts:PropMarketContract[]=[],rejected:PropMarketDiscovery['rejected']=[];
 for(const market of rawMarkets){const game=gameByEvent.get(market.event_ticker),series=seriesMap.get(String(market.event_ticker).split('-')[0]);if(!game||!series){if(rejected.length<1000)rejected.push({contractId:typeof market.ticker==='string'?market.ticker.slice(0,200):'unverified',reason:'The authoritative market event or series metadata could not be verified.'});continue;}const gameConfig=KALSHI_GAME_SERIES.find(s=>s.ticker===series.ticker),url=KALSHI_PROP_API+'/markets/'+encodeURIComponent(market.ticker),out=gameConfig?normalizeKalshiGameMarket(game,market,series,observedAt,url,gameTerms.get(gameConfig.terms)??null,targets):normalizeKalshiPropMarket(game,market,series,targets,observedAt,url,termsHash);if(out.contract)contracts.push(out.contract);else if(rejected.length<1000)rejected.push({contractId:typeof market.ticker==='string'?market.ticker.slice(0,200):'unverified',reason:out.reason!});}
 const unique=[...new Map(contracts.map(contract=>[contract.id,contract])).values()];
 return{contracts:unique,rejected,sources:sourceList,complete,status:{provider:'Kalshi',status:unique.length?(complete&&unique.every(c=>c.settlement.modelCompatible&&c.verification.current)?'available':'partial'):'unavailable',checkedAt:observedAt,contracts:unique.length,sourceUrl:KALSHI_PROP_DOCS,categories:[...new Set(unique.map(c=>c.category))],message:unique.length?'Verified public Kalshi player-stat contracts, separately labeled from DraftKings Predictions. Unsupported touchdown coverage, participation exceptions, missing fees and uncalibrated models withhold complete or unconditional value claims.':'No currently supported public player contracts could be verified. No replacement prices or statistics were invented.'} as PropProviderStatus};
}

/** Public discovery uses fixed documented exchange endpoints or an explicitly
 * authorized operator feed. A guest never supplies a URL, token or dataset. */
export async function discoverPlayerPropMarkets(games:PublicGame[],options:PropProviderOptions={}):Promise<PropMarketDiscovery>{
 const now=options.now??new Date(),observedAt=now.toISOString(),transport=options.transport??fetch;
 const upcoming=games.filter(game=>game.status!=='final'&&milliseconds(game.startTime)>now.getTime()&&milliseconds(game.startTime)<=now.getTime()+7*86400000).sort((a,b)=>milliseconds(a.startTime)-milliseconds(b.startTime)).slice(0,32);
 const key=sha({games:upcoming.map(g=>[g.id,g.home.id,g.away.id,g.startTime]),includeGameMarkets:options.includeGameMarkets===true,provider:options.provider??'legacy_all'});
 if(!options.force&&!options.transport&&cached?.key===key&&cached.until>now.getTime())return structuredClone(cached.value);
 if(!options.transport&&pending.has(key))return pending.get(key)!;
 const task=(async()=>{
  const notSelected=(provider:'DraftKings Predictions'|'Kalshi')=>({contracts:[] as PropMarketContract[],rejected:[],sources:[],complete:true,status:{provider,status:'unavailable' as const,checkedAt:observedAt,contracts:0,categories:[],sourceUrl:provider==='DraftKings Predictions'?'https://predictions.draftkings.com/en':KALSHI_PROP_DOCS,message:`${provider} was not queried in this explicitly selected ${options.provider} scan. No source substitution or equivalent-price claim is made.`}});
  const [dk,kalshi]=await Promise.all([options.provider==='Kalshi'?Promise.resolve(notSelected('DraftKings Predictions')):discoverDraftKings(upcoming,transport,observedAt,options.includeGameMarkets),options.provider==='DraftKings Predictions'?Promise.resolve(notSelected('Kalshi')):discoverKalshi(upcoming,transport,observedAt,options.includeGameMarkets)]);
  const contracts=[...dk.contracts,...kalshi.contracts],value:PropMarketDiscovery={contracts,providers:[dk.status,kalshi.status],sources:[...dk.sources,...kalshi.sources],checkedAt:observedAt,complete:dk.complete&&kalshi.complete,rejected:[...dk.rejected,...kalshi.rejected],neededGames:[...new Set(contracts.map(c=>c.gameId))]};
  if(!options.transport)cached={key,until:now.getTime()+CACHE_MS,value};return structuredClone(value);
 })().finally(()=>{if(!options.transport)pending.delete(key);});if(!options.transport)pending.set(key,task);return task;
}
export async function fetchPlayerPropMarkets(games:PublicGame[],catalog:PropPlayerIdentity[],options:PropProviderOptions={}):Promise<PropMarketDiscovery>{const value=await discoverPlayerPropMarkets(games,options);return{...value,contracts:value.contracts.map(contract=>contract.sourceKind==='public_exchange'?resolvePlayerPropIdentity(contract,catalog):resolveAuthorizedIdentity(contract,catalog))};}
function resolveAuthorizedIdentity(contract:PropMarketContract,catalog:PropPlayerIdentity[]):PropMarketContract{if(isGameMarket(contract.stat))return contract;const resolved=resolvePlayerPropIdentity(contract,catalog);if(resolved.playerId&&resolved.playerId!==contract.providerPlayerId)return{...resolved,playerId:null,mapping:{status:'conflict',method:'exact_GSIS_name_and_current_roster_team',reason:'The authorized source player ID disagrees with the current NFL roster.'}};return resolved;}
