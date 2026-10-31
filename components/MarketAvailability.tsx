'use client';

import {ArrowRight,ChevronRight,Clock3,Info,LoaderCircle,RefreshCw,ShieldCheck} from 'lucide-react';

export const DRAFTKINGS_NFL_URL='https://predictions.draftkings.com/en/markets/football/nfl';
type Counts={received:number;accepted:number;rejected:number;skippedOutOfScope:number;currentQuotes:number;compatibleContracts:number;closedContracts:number;unmappedIdentities:number};
type Diagnostic={code:string;stage:'configuration'|'source'|'contracts'|'identity';checkedAt:string;retryable:boolean;requiresOperator:boolean;httpStatus:number|null;message:string;action:string;counts?:Counts};
export type MarketSourceStatus={provider:string;status:string;checkedAt:string;message:string;diagnostic?:Diagnostic};
type Copy={title:string;badge:string;emptyTitle:string;message:string;action:string;checkedAt:string|null;retryable:boolean;requiresOperator:boolean;code:string;stage:string;httpStatus:number|null;counts?:Counts};
const time=(value:string|null)=>value&&Number.isFinite(Date.parse(value))?new Date(value).toLocaleString(undefined,{month:'short',day:'numeric',hour:'numeric',minute:'2-digit'}):'Time unavailable';
const kinds:Record<string,[string,string,string]>={
 feed_not_configured:['DraftKings feed not connected','Connection required','A market connection is required.'],
 authorization_not_configured:['DraftKings feed authorization is not configured','Authorization required','Authorized market access is required.'],
 feed_configuration_invalid:['DraftKings feed connection needs attention','Connection required','The source connection needs an operator update.'],
 credentials_missing:['The market source needs authorization','Authorization required','Authorized market access is required.'],
 authentication_failed:['DraftKings source authorization failed','Authorization failed','The source authorization needs an operator update.'],
 endpoint_not_found:['The market feed address could not be found','Connection required','The source connection needs an operator update.'],
 access_denied:['The market source denied access','Access denied','Authorized access must be verified.'],
 source_rate_limited:['DraftKings updates are temporarily paused','Rate limited','The source is limiting requests.'],
 source_timeout:['DraftKings market data is taking too long','Temporary interruption','The source check timed out.'],
 source_unavailable:['DraftKings market data is temporarily unavailable','Temporary interruption','The market source is temporarily unavailable.'],
 source_network_error:['The DraftKings source could not be reached','Temporary interruption','The source connection was interrupted.'],
 source_request_failed:['The DraftKings source request failed','Source check failed','The source response could not be verified.'],
 no_nfl_markets:['This feed returned no NFL contracts','Empty NFL feed','No NFL contracts were returned by this feed.'],
 no_requested_markets:['No contracts match this market view','No matching contracts','No contracts match this market view.'],
 unsupported_feed_schema:['The market feed format is not supported','Format needs support','A supported contract format is required.'],
 unsupported_pagination:['The contract listing pages need support','Listing needs verification','The contract listing could not be completed.'],
 pagination_incomplete:['The market listing is incomplete','Incomplete listing','Complete contract coverage is not verified.'],
 unsupported_response:['The market feed format needs an update','Verification required','The market response needs a supported format.'],
 unsupported_contracts:['These contract rules are not supported yet','Rules need verification','Supported contract definitions are needed.'],
 identity_verification_pending:['NFL identities are awaiting verification','Identity verification','Verified player and team identities are needed.'],
 identity_mismatch:['Player or team identity needs verification','Identity verification','Verified player and team identities are needed.'],
 stale_quotes:['Fresh DraftKings prices are not available','Stale quotes','Current quotes are needed for price comparisons.'],
 quotes_unavailable:['Current DraftKings prices are missing','Prices unavailable','Current quotes are needed for price comparisons.'],
 markets_not_open:['These contracts are not open for trading','Markets closed','There are no verified open contracts to analyze.'],
 partial_coverage:['Some DraftKings markets need more evidence','Partial coverage','Some contracts need additional verification.'],
 not_selected:['DraftKings is not selected for this research','Not selected','Select DraftKings to check its contracts.'],
 available:['DraftKings market access is verified','Verified source','Verified contract research will appear here.'],
};

/** Consumer copy follows structured verification evidence, never a guessed
 * diagnosis inferred from a generic availability flag or error message. */
export function marketAvailability(source:MarketSourceStatus|undefined,loading=false):Copy{
 const diagnostic=source?.diagnostic,code=diagnostic?.code??'unverified';
 const known=kinds[code],fallback=diagnostic?undefined:source?.status==='available'?kinds.available:source?.status==='partial'?kinds.partial_coverage:undefined;
 const state=known??fallback??['DraftKings availability is unverified','Not verified','DraftKings contract availability is unverified.'];
 return{title:loading&&!source?'Checking DraftKings market access':state[0],badge:loading&&!source?'Checking access':state[1],emptyTitle:state[2],
  message:diagnostic?.message??source?.message??(loading?'Checking the authorized market source.':'The app could not verify the current market source. Check its status before using market prices.'),
  action:code==='feed_not_configured'?'The app operator must connect an authorized event-contract data source before DraftKings market analysis can run.':diagnostic?.action??'Browse NFL games while verified market availability is checked.',checkedAt:diagnostic?.checkedAt??source?.checkedAt??null,
  retryable:diagnostic?.retryable===true,requiresOperator:diagnostic?.requiresOperator===true,code,stage:diagnostic?.stage??'unverified',httpStatus:diagnostic?.httpStatus??null,counts:diagnostic?.counts};
}

export default function MarketAvailability({source,loading=false,checking=false,onRetry,onManual,compact=false}:{source?:MarketSourceStatus;loading?:boolean;checking?:boolean;onRetry?:()=>void;onManual?:()=>void;compact?:boolean}){
 const state=marketAvailability(source,loading),verified=state.code==='available'||source?.status==='available'&&!source.diagnostic;
 return <section className={`market-availability ${compact?'compact':'detailed'} ${verified?'verified':''}`} aria-label="DraftKings Predictions source availability">
  <div className="market-availability-heading"><ShieldCheck size={compact?16:19}/><div><h3>{state.title}</h3>{!compact&&<span className={`tag ${verified?'cyan':'gold'}`}>{state.badge}</span>}</div></div>
  <p className="market-source-explanation">{state.message}</p>
  {state.stage==='configuration'&&<p className="market-unverified-listings">NFL contract listings have not been checked. An authorized source is required to verify which markets are available.</p>}
  {!compact&&<p className="market-availability-action">{state.action}</p>}
  <div className="market-availability-time"><Clock3 size={12}/><span>Checked {time(state.checkedAt)}</span>{state.requiresOperator&&<span className="market-operator-needed">App operator action required</span>}</div>
  <div className="market-availability-actions">
   {state.retryable&&onRetry&&<button className="btn" disabled={checking||loading} onClick={onRetry}>{checking?<LoaderCircle size={14} className="spin"/>:<RefreshCw size={14}/>} {checking?'Refreshing status…':'Refresh source status'}</button>}
   {compact?<a className="text-link" href="#markets">Market details <ChevronRight size={13}/></a>:<><a className="btn" href="#games">Browse NFL games <ArrowRight size={14}/></a>{onManual&&<button className="text-link" onClick={onManual}>Optional verified manual entry <ChevronRight size={13}/></button>}</>}
  </div>
  {!compact&&source?.diagnostic&&<details className="market-verification-details"><summary><Info size={13}/> Verification details</summary><dl><dt>Check result</dt><dd>{state.badge}</dd><dt>Check stage</dt><dd>{state.stage==='configuration'?'App connection':state.stage==='source'?'Market source':state.stage==='identity'?'Player / team identity':'Contract definitions'}</dd>{state.httpStatus!==null&&<><dt>Source response</dt><dd>HTTP {state.httpStatus}</dd></>}{state.counts&&Object.entries({received:'Contracts received',accepted:'Contracts accepted',rejected:'Contracts withheld',skippedOutOfScope:'Outside this market view',currentQuotes:'Current quotes',compatibleContracts:'Supported rules',closedContracts:'Closed contracts',unmappedIdentities:'Unverified identities'}).map(([key,label])=>{const count=state.counts![key as keyof Counts];return typeof count==='number'&&Number.isFinite(count)&&count>=0?<div className="market-check-count" key={key}><dt>{label}</dt><dd>{count.toLocaleString()}</dd></div>:null;})}</dl></details>}
 </section>;
}
