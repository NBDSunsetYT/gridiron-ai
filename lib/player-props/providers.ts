import {isIP} from 'node:net';
import {performance} from 'node:perf_hooks';
import {z} from 'zod';
import {source,sha} from '../public-nfl/sources';
import type {ResearchSource,PublicGame} from '../public-nfl/types';
import type {PropMarketContract,PropMarketDiscovery,PropPlayerIdentity,PropProviderOptions,PropProviderStatus,PropProviderDiagnostic,PropProviderDiagnosticCode} from './market-types';
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
type SourceFailure='http'|'response_too_large'|'empty_response'|'invalid_json'|'unsupported_feed_schema'|'unsupported_pagination';
class ProviderSourceError extends Error{
 constructor(readonly reason:SourceFailure,readonly httpStatus:number|null=null,readonly retryAfterSeconds:number|null=null){super('The authorized market response could not be verified.');this.name='ProviderSourceError';}
}
/** Public diagnostics contain fixed explanations and observations, never a
 * configured endpoint, provider error body, server token or raw exception. */
function diagnostic(code:PropProviderDiagnosticCode,checkedAt:string,message:string,action:string,options:Partial<PropProviderDiagnostic>={}):PropProviderDiagnostic{return{code,stage:'source',checkedAt,retryable:false,requiresOperator:false,httpStatus:null,message,action,...options};}
export function draftKingsConfigurationDiagnostic(observedAt:string=new Date().toISOString()):PropProviderDiagnostic|null{
 const endpoint=process.env.GRIDIRON_DK_PREDICTIONS_FEED_URL,authorized=process.env.GRIDIRON_DK_PREDICTIONS_FEED_AUTHORIZED==='1';
 if(!endpoint)return diagnostic('feed_not_configured',observedAt,'The app has no authorized DraftKings Predictions NFL contract feed connected.','An app operator must connect an authorized event-contract data source. You do not need a Supabase dashboard account or sportsbook password.',{stage:'configuration',requiresOperator:true,missingConfiguration:authorized?['feed']:['feed','authorization']});
 if(!authorized)return diagnostic('authorization_not_configured',observedAt,'A DraftKings Predictions feed connection was entered, but its data-access authorization has not been confirmed.','The app operator must confirm the source is authorized before the app can request its contracts.',{stage:'configuration',requiresOperator:true,missingConfiguration:['authorization']});
 try{configuredFeedUrl();return null;}catch{return diagnostic('feed_configuration_invalid',observedAt,'The authorized feed connection is configured incorrectly. No request was sent to it.','The app operator must correct the secure feed connection. No private endpoint or credential is shown here.',{stage:'configuration',requiresOperator:true});}
}
async function readBytes(url:string,transport:typeof fetch,headers:Record<string,string>={},maximum=MAX_SOURCE_BYTES,onStatus?:(status:number)=>void){
 const response=await transport(url,{method:'GET',headers:{Accept:'application/json,application/pdf,*/*',...headers},cache:'no-store',redirect:'error',signal:AbortSignal.timeout(10000)});
 onStatus?.(response.status);
 if(!response.ok){const raw=response.headers.get('retry-after'),retry=raw&&/^\d{1,6}$/.test(raw)?Math.min(86400,Number(raw)):null;await response.body?.cancel().catch(()=>{});throw new ProviderSourceError('http',response.status,retry);}
 if(Number(response.headers.get('content-length')||0)>maximum){await response.body?.cancel().catch(()=>{});throw new ProviderSourceError('response_too_large',response.status);}
 const reader=response.body?.getReader();if(!reader)throw new ProviderSourceError('empty_response',response.status);
 const chunks:Uint8Array[]=[];let size=0;
 for(;;){const {done,value}=await reader.read();if(done)break;size+=value.byteLength;if(size>maximum){await reader.cancel();throw new ProviderSourceError('response_too_large',response.status);}chunks.push(value);}
 return Buffer.concat(chunks);
}
async function readJson(url:string,transport:typeof fetch,headers:Record<string,string>={},maximum=MAX_SOURCE_BYTES,onStatus?:(status:number)=>void):Promise<any>{let status:number|null=null;const bytes=await readBytes(url,transport,headers,maximum,s=>{status=s;onStatus?.(s);});try{return JSON.parse(bytes.toString('utf8'));}catch{throw new ProviderSourceError('invalid_json',status);}}
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
 const token=process.env.GRIDIRON_DK_PREDICTIONS_FEED_TOKEN;
 if(url.protocol!=='https:'||url.username||url.password||url.port&&url.port!=='443'||isIP(host)||host==='localhost'||host.endsWith('.localhost')||host.endsWith('.local')||!host.includes('.')||[...url.searchParams.keys()].some(key=>/token|key|secret|password|signature|authorization/i.test(key))||Boolean(token&&(raw.includes(token)||/[\r\n]/.test(token))))throw Error('The authorized feed URL must use a public HTTPS host and server-side header credentials.');
 return url;
}
export const DRAFTKINGS_PREDICTIONS_NFL_URL='https://predictions.draftkings.com/en/markets/football/nfl';
function safeRejectedId(value:unknown){const token=process.env.GRIDIRON_DK_PREDICTIONS_FEED_TOKEN;return typeof value==='string'&&/^[A-Za-z0-9._:/-]{1,200}$/.test(value)&&(!token||!value.includes(token))?value:'unverified';}
function contractFailure(error:unknown):'identity_mismatch'|'unsupported_contracts'{
 const identityMessages=new Set(['Contract matchup, kickoff or team disagrees with the verified schedule.','The exact GSIS player, roster name and team mapping could not be verified.','The exact scheduled game and team could not be verified.']);
 if(error instanceof Error&&identityMessages.has(error.message))return'identity_mismatch';
 if(error instanceof z.ZodError){if(error.issues.some(issue=>['provider','marketType','stat','settlement','rules','rulesUrl','sourceUrl'].includes(String(issue.path[0]))))return'unsupported_contracts';if(error.issues.some(issue=>['playerId','playerName','gameId','eventStart','team'].includes(String(issue.path[0]))))return'identity_mismatch';}
 return'unsupported_contracts';
}
function sourceFailureDiagnostic(error:unknown,observedAt:string):PropProviderDiagnostic{
 const retry='The app can retry this source later. No alternative prices have been substituted.',operator='The app operator must review the authorized source connection with its provider; no sportsbook password is needed.';
 if(error instanceof ProviderSourceError){
  const status=error.httpStatus,extra={httpStatus:status};
  if(error.reason==='http'){
   if(status===401){const missing=!process.env.GRIDIRON_DK_PREDICTIONS_FEED_TOKEN;return diagnostic(missing?'credentials_missing':'authentication_failed',observedAt,missing?'The configured feed returned HTTP401 and no server credential is configured.':'The configured feed rejected the server authentication with HTTP401.',operator,{...extra,requiresOperator:true});}
   if(status===403)return diagnostic('access_denied',observedAt,'The configured feed denied access with HTTP403. The response does not establish whether entitlement, region or another access rule caused it.',operator,{...extra,requiresOperator:true});
   if(status===404)return diagnostic('endpoint_not_found',observedAt,'The configured feed endpoint returned HTTP404. This is not evidence that DraftKings has no NFL markets.',operator,{...extra,requiresOperator:true});
   if(status===429)return diagnostic('source_rate_limited',observedAt,'The authorized feed is temporarily rate limited (HTTP429).',retry,{...extra,retryable:true,retryAfterSeconds:error.retryAfterSeconds});
   if(status===408||status===504)return diagnostic('source_timeout',observedAt,'The authorized feed request timed out.',retry,{...extra,retryable:true});
   if(status!==null&&status>=500)return diagnostic('source_unavailable',observedAt,'The authorized feed returned a server error. Current contracts could not be verified.',retry,{...extra,retryable:true});
   return diagnostic('source_request_failed',observedAt,'The authorized feed rejected the request. Its response does not establish an empty NFL market list.',operator,{...extra,requiresOperator:true});
  }
  if(error.reason==='unsupported_feed_schema')return diagnostic('unsupported_feed_schema',observedAt,'The feed responded, but its provider identity or contract schema does not match the supported DraftKings Predictions event-contract format.',operator,{...extra,requiresOperator:true});
  if(error.reason==='unsupported_pagination')return diagnostic('unsupported_pagination',observedAt,'The feed returned unsupported or repeating pagination. Complete NFL contract coverage could not be verified.',operator,{...extra,requiresOperator:true});
  return diagnostic('unsupported_response',observedAt,error.reason==='response_too_large'?'The authorized feed response exceeded its safe ingestion bound.':error.reason==='empty_response'?'The authorized feed returned no readable response body.':'The authorized feed did not return a valid JSON response.',operator,{...extra,requiresOperator:true});
 }
 const name=error&&typeof error==='object'&&'name'in error?String(error.name):'',code=error&&typeof error==='object'&&'code'in error?String(error.code):'';
 if(name==='TimeoutError'||name==='AbortError'||code==='ETIMEDOUT')return diagnostic('source_timeout',observedAt,'The authorized feed request did not finish before its timeout.',retry,{retryable:true});
 return diagnostic('source_network_error',observedAt,'The app could not establish a verified response from the configured feed. No HTTP access decision or empty market list was received.',retry,{retryable:true});
}
async function discoverDraftKings(games:PublicGame[],transport:typeof fetch,observedAt:string,includeGames=false):Promise<{contracts:PropMarketContract[];status:PropProviderStatus;sources:ResearchSource[];rejected:PropMarketDiscovery['rejected'];complete:boolean}>{
 const info:Omit<PropProviderStatus,'status'|'message'>={provider:'DraftKings Predictions',checkedAt:observedAt,contracts:0,sourceUrl:DRAFTKINGS_PREDICTIONS_NFL_URL,categories:[]},configuration=draftKingsConfigurationDiagnostic(observedAt);
 if(configuration)return{contracts:[],status:{...info,status:'unavailable',message:configuration.message,diagnostic:configuration},sources:[],rejected:[],complete:true};
 const contracts:PropMarketContract[]=[],rejected:PropMarketDiscovery['rejected']=[],states=new Map<string,string>();let complete=true,received=0,skippedOutOfScope=0,httpStatus:number|null=null,identityRejected=0;
 const counts=(unique:PropMarketContract[])=>({received,accepted:unique.length,rejected:rejected.length,skippedOutOfScope,currentQuotes:unique.filter(c=>c.verification.current).length,compatibleContracts:unique.filter(c=>c.settlement.modelCompatible).length,closedContracts:unique.filter(c=>states.get(c.id)!=='open').length,unmappedIdentities:unique.filter(c=>!isGameMarket(c.stat)&&c.mapping.status!=='verified').length,duplicates:contracts.length-unique.length});
 try{
  const base=configuredFeedUrl()!,headers:Record<string,string>={};if(process.env.GRIDIRON_DK_PREDICTIONS_FEED_TOKEN)headers.Authorization='Bearer '+process.env.GRIDIRON_DK_PREDICTIONS_FEED_TOKEN;
  let cursor:string|undefined;
  for(let page=0;page<MAX_PAGES;page++){
   const url=new URL(base);if(cursor)url.searchParams.set('cursor',cursor);
   const body=await readJson(url.href,transport,headers,MAX_SOURCE_BYTES,status=>{httpStatus=status;});
   if(!['gridiron-player-prop-contracts-v1','gridiron-nfl-event-contracts-v1'].includes(body?.schema)||body.provider!=='DraftKings Predictions'||!Array.isArray(body.contracts)||body.contracts.length>1000)throw new ProviderSourceError('unsupported_feed_schema',httpStatus);
   received+=body.contracts.length;
   for(const value of body.contracts){
    if(!includeGames&&isGameMarket(String(value?.stat))){skippedOutOfScope++;continue;}
    try{const contract=normalizeAuthorizedPropContract(value,games,[],observedAt);contracts.push(contract);states.set(contract.id,value.status);}catch(error){const reason=contractFailure(error);if(reason==='identity_mismatch')identityRejected++;rejected.push({contractId:safeRejectedId(value?.contractId),reason:reason==='identity_mismatch'?'The contract identity could not be matched to the verified NFL schedule or required identity fields.':'The contract price, threshold, rules or safe event-contract definition could not be verified.'});}
   }
   if(body.nextCursor===null||body.nextCursor===undefined||body.nextCursor===''){cursor=undefined;break;}
   if(typeof body.nextCursor!=='string'||body.nextCursor.length>500||body.nextCursor===cursor)throw new ProviderSourceError('unsupported_pagination',httpStatus);cursor=body.nextCursor;if(page===MAX_PAGES-1)complete=false;
  }
  const unique=[...new Map(contracts.map(c=>[c.id,c])).values()],coverage=counts(unique),pricePresent=unique.some(c=>Boolean(c.yesAskCents||c.noAskCents||c.displayedYesPercent!=null||c.displayedNoPercent!=null));
  let report:PropProviderDiagnostic;
  if(!complete)report=diagnostic('pagination_incomplete',observedAt,'The authorized feed still has additional pages after the bounded refresh. This is partial coverage, not evidence that no NFL markets exist.','The app operator must review pagination or narrow the authorized feed scope.',{stage:'source',requiresOperator:true,httpStatus});
  else if(received===0)report=diagnostic('no_nfl_markets',observedAt,'The authorized feed responded successfully and returned an empty NFL contract list for this request.','Check again when the provider lists NFL contracts; reconnecting accounts is not required.',{stage:'contracts',httpStatus});
  else if(skippedOutOfScope===received)report=diagnostic('no_requested_markets',observedAt,'The connected feed returned NFL contracts, but none belong to the requested player-market scope.','Choose all NFL markets to inspect the available game contracts.',{stage:'contracts',httpStatus});
  else if(!unique.length)report=diagnostic(identityRejected===rejected.length?'identity_mismatch':'unsupported_contracts',observedAt,identityRejected===rejected.length?'NFL contracts were returned, but none could be matched to the verified schedule or required player/team identity.':'NFL contracts were returned, but all were rejected because their exact definitions, prices or rules could not be verified.','The app operator must review the rejected contract definitions. No missing record is treated as an empty NFL market list.',{stage:identityRejected===rejected.length?'identity':'contracts',requiresOperator:true,httpStatus});
  else if(coverage.closedContracts===unique.length)report=diagnostic('markets_not_open',observedAt,'The connected feed returned verified NFL contracts, but all are closed or suspended.','Wait for the source to list open markets; historical contracts are not called current.',{stage:'contracts',httpStatus});
  else if(!pricePresent)report=diagnostic('quotes_unavailable',observedAt,'The connected feed returned NFL contract definitions without a displayed percentage or quoted offer.','The provider must supply current prices before market comparisons can be shown.',{stage:'contracts',httpStatus});
  else if(!coverage.currentQuotes)report=diagnostic('stale_quotes',observedAt,'The connected feed returned NFL prices, but none passes the current quote timestamp and open-market checks.','Refresh verified source prices. Saved observations remain historical.',{stage:'contracts',httpStatus,retryable:true});
  else if(!coverage.compatibleContracts)report=diagnostic('unsupported_contracts',observedAt,'The authorized feed is connected and returned NFL prices, but none of the verified settlement definitions is supported by the current model.','The contracts remain identified; unsupported model probabilities and valuations are withheld.',{stage:'contracts',httpStatus});
  else if(rejected.length||coverage.compatibleContracts<unique.length||coverage.currentQuotes<unique.length)report=diagnostic('partial_coverage',observedAt,'The authorized feed is connected. Some returned contracts have unsupported definitions or lack a current verified quote.','Inspect each contract’s evidence and limitations. Unsupported outcomes remain withheld.',{stage:'contracts',httpStatus});
  else report=diagnostic('available',observedAt,'Current authorized DraftKings Predictions event-contract definitions and prices were verified.','Player identity, fees, settlement exceptions and model support are checked separately before analysis.',{stage:'contracts',httpStatus});
  report={...report,counts:coverage,...identityRejected?{issues:[{code:'identity_mismatch' as const,contracts:identityRejected}]}:{}};
  const status=report.code==='available'||report.code==='no_nfl_markets'||report.code==='no_requested_markets'?'available':'partial';
  return{contracts:unique,status:{...info,status,contracts:unique.length,categories:[...new Set(unique.map(c=>c.category))],message:report.message,diagnostic:report},sources:[source('dk-authorized-player-props','Authorized DraftKings Predictions contract feed',cleanUrl(base),observedAt,complete?'available':'partial','Operator-authorized event-contract integration; not a public DraftKings API or sportsbook substitution.')],rejected,complete};
 }catch(error){const unique=[...new Map(contracts.map(c=>[c.id,c])).values()],report={...sourceFailureDiagnostic(error,observedAt),counts:counts(unique)};return{contracts:[],status:{...info,status:'unavailable',message:report.message,diagnostic:report},sources:[],rejected,complete:false};}
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
 const key=sha({games:upcoming.map(g=>[g.id,g.home.id,g.away.id,g.startTime]),includeGameMarkets:options.includeGameMarkets===true,provider:options.provider??'legacy_all',configuration:sha({url:process.env.GRIDIRON_DK_PREDICTIONS_FEED_URL??null,authorization:process.env.GRIDIRON_DK_PREDICTIONS_FEED_AUTHORIZED??null,token:process.env.GRIDIRON_DK_PREDICTIONS_FEED_TOKEN??null})});
 if(!options.force&&!options.transport&&cached?.key===key&&cached.until>now.getTime())return structuredClone(cached.value);
 if(!options.transport&&pending.has(key))return pending.get(key)!;
 const task=(async()=>{
  const notSelected=(provider:'DraftKings Predictions'|'Kalshi')=>{const message=`${provider} was not queried in this explicitly selected ${options.provider} scan. No source substitution or equivalent-price claim is made.`,report=diagnostic('not_selected',observedAt,message,'Select this provider explicitly to check its own authorized data connection.');return{contracts:[] as PropMarketContract[],rejected:[],sources:[],complete:true,status:{provider,status:'unavailable' as const,checkedAt:observedAt,contracts:0,categories:[],sourceUrl:provider==='DraftKings Predictions'?DRAFTKINGS_PREDICTIONS_NFL_URL:KALSHI_PROP_DOCS,message,diagnostic:report}};};
  const [dk,kalshi]=await Promise.all([options.provider==='Kalshi'?Promise.resolve(notSelected('DraftKings Predictions')):discoverDraftKings(upcoming,transport,observedAt,options.includeGameMarkets),options.provider==='DraftKings Predictions'?Promise.resolve(notSelected('Kalshi')):discoverKalshi(upcoming,transport,observedAt,options.includeGameMarkets)]);
  const contracts=[...dk.contracts,...kalshi.contracts],value:PropMarketDiscovery={contracts,providers:[dk.status,kalshi.status],sources:[...dk.sources,...kalshi.sources],checkedAt:observedAt,complete:dk.complete&&kalshi.complete,rejected:[...dk.rejected,...kalshi.rejected],neededGames:[...new Set(contracts.map(c=>c.gameId))]};
  if(!options.transport)cached={key,until:now.getTime()+CACHE_MS,value};return structuredClone(value);
 })().finally(()=>{if(!options.transport)pending.delete(key);});if(!options.transport)pending.set(key,task);return task;
}
export async function fetchPlayerPropMarkets(games:PublicGame[],catalog:PropPlayerIdentity[],options:PropProviderOptions={}):Promise<PropMarketDiscovery>{
 const value=await discoverPlayerPropMarkets(games,options),contracts=value.contracts.map(contract=>contract.sourceKind==='public_exchange'?resolvePlayerPropIdentity(contract,catalog):resolveAuthorizedIdentity(contract,catalog));
 const providers=value.providers.map(provider=>{
  if(provider.provider!=='DraftKings Predictions'||!provider.diagnostic)return provider;
  const playerContracts=contracts.filter(c=>c.provider==='DraftKings Predictions'&&!isGameMarket(c.stat));
  if(!catalog.length){if(!playerContracts.length||!['available','partial_coverage'].includes(provider.diagnostic.code))return provider;const report=diagnostic('identity_verification_pending',value.checkedAt,'The authorized feed is connected, but a verified NFL roster catalog is not available to check these player identities.','The app must refresh verified roster evidence before publishing those player predictions; no identity or statistics are guessed.',{stage:'identity',httpStatus:provider.diagnostic.httpStatus,retryable:true,counts:provider.diagnostic.counts});return{...provider,status:'partial' as const,message:report.message,diagnostic:report};}
  const failed=contracts.filter(c=>c.provider==='DraftKings Predictions'&&!isGameMarket(c.stat)&&c.mapping.status!=='verified').length;if(!failed)return{...provider,diagnostic:{...provider.diagnostic,...provider.diagnostic.counts?{counts:{...provider.diagnostic.counts,unmappedIdentities:0}}:{}}};
  const issue={code:'identity_mismatch' as const,contracts:failed},existing=provider.diagnostic.issues??[],issues=[...existing.filter(v=>v.code!=='identity_mismatch'),{...issue,contracts:failed+existing.filter(v=>v.code==='identity_mismatch').reduce((n,v)=>n+v.contracts,0)}],counts=provider.diagnostic.counts?{...provider.diagnostic.counts,unmappedIdentities:failed}:undefined;
  const replace=['available','partial_coverage'].includes(provider.diagnostic.code),conflict=playerContracts.some(c=>c.mapping.status==='conflict'),report=replace?diagnostic('identity_mismatch',value.checkedAt,'The authorized feed is connected, but some player contracts could not be matched uniquely to the verified NFL roster and source player ID.','The affected predictions are withheld until the app can verify the exact player identity. Game contracts and verified players remain separate.',{stage:'identity',httpStatus:provider.diagnostic.httpStatus,requiresOperator:conflict,retryable:!conflict}):provider.diagnostic;
  return{...provider,status:'partial' as const,message:report.message,diagnostic:{...report,...counts?{counts}:{},issues}};
 });
 return{...value,contracts,providers};
}
function resolveAuthorizedIdentity(contract:PropMarketContract,catalog:PropPlayerIdentity[]):PropMarketContract{if(isGameMarket(contract.stat))return contract;const resolved=resolvePlayerPropIdentity(contract,catalog);if(resolved.playerId&&resolved.playerId!==contract.providerPlayerId)return{...resolved,playerId:null,mapping:{status:'conflict',method:'exact_GSIS_name_and_current_roster_team',reason:'The authorized source player ID disagrees with the current NFL roster.'}};return resolved;}
