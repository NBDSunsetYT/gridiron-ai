import Decimal from 'decimal.js';
import {ApiError} from '../auth';
import {buildFinancialReport,type ReportPeriod} from '../reports';
import {filterRecordedWagers,type RecordedWagerSport} from '../wager-performance';

type Metric='withdrawals'|'deposits'|'realized_pl'|'balance';
type Row=Record<string,any>;
export type AccountReportIntent={metrics:Metric[];period:ReportPeriod;sportsbook:'all'|'DraftKings'|'Hard Rock';sport?:RecordedWagerSport};
/** Narrow account questions get exact database arithmetic, never guessed NFL
 * analysis. Unsupported dates and mixed research questions require the normal
 * assistant instead of silently changing the requested reporting period. */
export function accountReportIntent(question:string):AccountReportIntent|null{
 const q=question.normalize('NFKC').toLowerCase().trim();
 if(!/\b(?:my|i|me)\b/.test(q)||! /^(?:please\s+)?(?:how\s+much|what(?:'s| is| are)|show|tell\s+me|give\s+me)\b/.test(q))return null;
 if(/\b(?:player|game|prediction|contract|model|odds|market|simulate|receiving|passing|rushing|compare)\b/.test(q))return null;
 if(/\b(?:last|past|previous|prior|ago|next|tomorrow|yesterday|since|between|quarter|season|weekly|monthly|annually|average|january|february|march|april|may|june|july|august|september|october|november|december)\b|\d{4}-\d{2}|\b\d{4}\b/.test(q))return null;
 const metrics:Metric[]=[];
 if(/\b(?:withdrawals?|withdrawn|withdrew|withdraw)\b/.test(q))metrics.push('withdrawals');
 if(/\bdeposits?\b|\bdeposited\b/.test(q))metrics.push('deposits');
 if(/\brealized\b/.test(q)&&/(?:\bp\s*[\/_&-]\s*l\b|\bprofit\b|\bloss\b)/.test(q))metrics.push('realized_pl');
 if(/\bbalance\b|\bmy\s+(?:current\s+)?bankroll\b|\bavailable\b.*\bwallet\b/.test(q))metrics.push('balance');
 if(!metrics.length)return null;
 const periods:Array<[RegExp,ReportPeriod]>=[[/\bthis\s+month\b/,'month'],[/\bthis\s+week\b/,'week'],[/\btoday\b/,'day'],[/\bthis\s+year\b/,'year']];
 const matches=periods.filter(([pattern])=>pattern.test(q));if(matches.length>1)return null;
 const draft=/\bdraft\s*kings\b/.test(q),hard=/\bhard\s*rock\b/.test(q);
 const cfb=/\b(?:cfb|ncaa|college\s+football)\b/.test(q),nfl=/\bnfl\b/.test(q),unspecified=/\bunspecified\b/.test(q);
 const sport:RecordedWagerSport|undefined=cfb&&!nfl?'CFB':nfl&&!cfb?'NFL':unspecified?'Unspecified':undefined;
 return{metrics,period:matches[0]?.[1]??'all',sportsbook:draft&&!hard?'DraftKings':hard&&!draft?'Hard Rock':'all',...sport?{sport}:{}};
}
function exact(value:unknown){if(!Number.isSafeInteger(value))throw new ApiError('An exact recorded account amount could not be verified.',503);return Number(value);}
const money=(value:number)=>`${value<0?'-':''}$${new Decimal(value).abs().div(100).toFixed(2)}`;
export function calculateAccountReport(ledger:Row,settings:Row,intent:AccountReportIntent,now=new Date()){
 const timezone=typeof settings.timezone==='string'?settings.timezone:'UTC';
 let report:ReturnType<typeof buildFinancialReport>;
 try{const input=intent.sport?{...ledger,bets:filterRecordedWagers(ledger.bets??[],{sport:intent.sport})}:ledger;report=buildFinancialReport(input as any,{timezone,period:intent.period,sportsbook:intent.sportsbook,now});}catch{throw new ApiError('The recorded financial report or account timezone could not be verified. Review Wallet settings before retrying.',503);}
 const period=intent.period==='all'?'all recorded dates':intent.period==='day'?'today':`this ${intent.period}`;
 const scope=intent.sportsbook==='all'?'Combined DraftKings and Hard Rock records':`${intent.sportsbook} records`;
 const account=intent.sportsbook==='all'?ledger.summary:ledger.accounts?.find((row:Row)=>row.sportsbook===intent.sportsbook);
 const lines=['Calculated account report',scope+'.'];
 if(intent.sport)lines.push(`Wager-result filter: ${intent.sport}. Account cash, deposits, withdrawals and transfers remain combined across sports. Records without sport metadata remain Unspecified.`);
 const values:Record<string,number>={};
 for(const metric of intent.metrics){
  if(metric==='withdrawals'){values.totalWithdrawalsCents=exact(report.totals.withdrawalsCents);lines.push(`Recorded withdrawals for ${period}: ${money(values.totalWithdrawalsCents)}.`);}
  if(metric==='deposits'){values.totalDepositsCents=exact(report.totals.depositsCents);lines.push(`Recorded deposits for ${period}: ${money(values.totalDepositsCents)}.`);}
  if(metric==='realized_pl'){values.realizedPlCents=exact(report.totals.realizedPlCents);lines.push(`Realized betting P/L for ${period}: ${money(values.realizedPlCents)}. This uses actual recorded payouts minus stakes on settlement dates. Deposits, withdrawals and transfers are excluded.`);}
  if(metric==='balance'){
   values.cashBalanceCents=exact(account?.cashBalanceCents);values.availableBalanceCents=exact(account?.availableBalanceCents);values.pendingExposureCents=exact(account?.pendingExposureCents);
   lines.push(`Current recorded bankroll: ${money(values.cashBalanceCents)}; available balance: ${money(values.availableBalanceCents)}; pending exposure: ${money(values.pendingExposureCents)}.`);
  }
 }
 if(intent.period!=='all'&&intent.metrics.some(metric=>metric!=='balance'))lines.push(`Account timezone: ${report.timezone}. Local reporting dates: ${report.bounds.from} through ${report.bounds.toExclusive} (end excluded).`);
 lines.push(`Read from your GRIDIRON AI ledger at ${report.generatedAt}. These are your recorded account figures; no sportsbook balance was fetched. No language-model response was used.`);
 const relevantDates=[...(ledger.transactions??[]).map((row:Row)=>row.date),...(ledger.bets??[]).map((row:Row)=>row.settledAt)].filter((value:unknown):value is string=>typeof value==='string'&&Number.isFinite(Date.parse(value))).sort();
 const citation={id:'read_ledger',timestamp:report.generatedAt,source:'Authenticated owner-scoped GRIDIRON AI ledger',timezone:report.timezone,sportsbook:intent.sportsbook,...intent.sport?{sport:intent.sport}:{},period:report.bounds,latestRecordedDate:relevantDates.at(-1)??null};
 return{text:lines.join('\n\n'),generatedByAI:false as const,method:'calculated_account_report' as const,values,timezone:report.timezone,period:report.bounds,citations:[citation],generatedAt:report.generatedAt};
}
