/** Financial reporting uses settlement dates and exact cents. No capital movement is betting profit. */
export type ReportPeriod='day'|'week'|'month'|'year'|'all';
type Row=Record<string,any>;
export type FinancialDay={date:string;realizedPlCents:number;settledStakeCents:number;settledBets:number;voidedBets:number;wagerStakePlacedCents:number;depositsCents:number;withdrawalsCents:number;startingBalanceCents:number;promotionalCreditsCents:number;adjustmentsCents:number;refundsCents:number;transfersOutCents:number;netCashContributedCents:number;roi:number|null};
const validPeriods:ReportPeriod[]=['day','week','month','year','all'];
function exact(value:unknown){if(!Number.isSafeInteger(value))throw Error('Financial report requires exact integer cents.');return Number(value);}
function add(a:number,b:number){const total=a+b;if(!Number.isSafeInteger(total))throw Error('Financial report exceeds the exact arithmetic range.');return total;}
export function localDateKey(value:string|Date,timezone:string){
 const d=value instanceof Date?value:new Date(value);if(!Number.isFinite(d.getTime()))throw Error('Invalid financial record timestamp.');
 const parts=new Intl.DateTimeFormat('en-US',{timeZone:timezone,year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(d);
 const p=Object.fromEntries(parts.map(x=>[x.type,x.value]));return `${p.year}-${p.month}-${p.day}`;
}
function dateOnly(value:string){if(!/^\d{4}-\d{2}-\d{2}$/.test(value)||new Date(value+'T00:00:00Z').toISOString().slice(0,10)!==value)throw Error('Use a valid YYYY-MM-DD anchor.');return value;}
function shift(value:string,days:number){const d=new Date(value+'T00:00:00Z');d.setUTCDate(d.getUTCDate()+days);return d.toISOString().slice(0,10);}
function emptyDay(date:string):FinancialDay{return{date,realizedPlCents:0,settledStakeCents:0,settledBets:0,voidedBets:0,wagerStakePlacedCents:0,depositsCents:0,withdrawalsCents:0,startingBalanceCents:0,promotionalCreditsCents:0,adjustmentsCents:0,refundsCents:0,transfersOutCents:0,netCashContributedCents:0,roi:null};}
export function reportBounds(period:ReportPeriod,anchor:string){
 dateOnly(anchor);if(!validPeriods.includes(period))throw Error('Choose day, week, month, year or all.');
 if(period==='day')return{from:anchor,toExclusive:shift(anchor,1)};
 if(period==='week'){const day=new Date(anchor+'T00:00:00Z').getUTCDay(),from=shift(anchor,-((day+6)%7));return{from,toExclusive:shift(from,7)};}
 if(period==='month'){const from=anchor.slice(0,7)+'-01',d=new Date(from+'T00:00:00Z');d.setUTCMonth(d.getUTCMonth()+1);return{from,toExclusive:d.toISOString().slice(0,10)};}
 if(period==='year')return{from:anchor.slice(0,4)+'-01-01',toExclusive:String(Number(anchor.slice(0,4))+1)+'-01-01'};
 return{from:null,toExclusive:null};
}
export function buildFinancialReport(ledger:{bets:Row[];transactions:Row[];accounts?:Row[]},options:{timezone?:string;period?:ReportPeriod;anchor?:string;sportsbook?:string;now?:Date}={}){
 const timezone=options.timezone||'UTC',period=options.period||'month',now=options.now||new Date();
 // Validate zone even on an empty account. Daily comparisons use local date keys across DST changes.
 const today=localDateKey(now,timezone),anchor=dateOnly(options.anchor||today),bounds=reportBounds(period,anchor),book=options.sportsbook||'all';
 if(!['all','DraftKings','Hard Rock'].includes(book))throw Error('Choose all, DraftKings or Hard Rock.');
 const map=new Map<string,FinancialDay>(),get=(date:string)=>{if(!map.has(date))map.set(date,emptyDay(date));return map.get(date)!;};
 for(const bet of ledger.bets){if(book!=='all'&&bet.sportsbook!==book)continue;const placed=get(localDateKey(bet.placedAt,timezone));placed.wagerStakePlacedCents=add(placed.wagerStakePlacedCents,exact(bet.stakeCents));
  if(bet.result==='pending')continue;if(!bet.settledAt)throw Error('A settled wager is missing its settlement timestamp.');
  const day=get(localDateKey(bet.settledAt,timezone)),stake=exact(bet.stakeCents),payout=exact(bet.payoutCents);day.realizedPlCents=add(day.realizedPlCents,payout-stake);
  if(bet.result==='voided')day.voidedBets++;else{day.settledStakeCents=add(day.settledStakeCents,stake);day.settledBets++;}
 }
 const typeField:Record<string,keyof FinancialDay>={deposit:'depositsCents',withdrawal:'withdrawalsCents',starting_balance:'startingBalanceCents',promotional_credit:'promotionalCreditsCents',adjustment:'adjustmentsCents',refund:'refundsCents',transfer:'transfersOutCents'};
 for(const tx of ledger.transactions){if(tx.reversed||tx.type==='reversal'||!typeField[tx.type]||(book!=='all'&&tx.sportsbook!==book))continue;const day=get(localDateKey(tx.date,timezone)),field=typeField[tx.type],cents=exact(tx.amountCents);(day[field] as number)=add(day[field] as number,cents);}
 for(const d of map.values()){d.netCashContributedCents=add(add(d.startingBalanceCents,d.depositsCents),-d.withdrawalsCents);d.roi=d.settledStakeCents?d.realizedPlCents/d.settledStakeCents:null;}
 const allDays=[...map.values()].sort((a,b)=>a.date.localeCompare(b.date)),days=allDays.filter(d=>(!bounds.from||d.date>=bounds.from)&&(!bounds.toExclusive||d.date<bounds.toExclusive));
 const totals=emptyDay('TOTAL');for(const d of days)for(const key of Object.keys(totals) as (keyof FinancialDay)[])if(key!=='date'&&key!=='roi')(totals[key] as number)=add(totals[key] as number,d[key] as number);totals.roi=totals.settledStakeCents?totals.realizedPlCents/totals.settledStakeCents:null;
 const monthBounds=reportBounds('month',anchor),calendar:FinancialDay[]=[];for(let date=monthBounds.from!;date<monthBounds.toExclusive!;date=shift(date,1))calendar.push(map.get(date)||emptyDay(date));
 return{timezone,period,anchor,today,sportsbook:book,bounds,totals,days,calendar,calendarMonth:anchor.slice(0,7),generatedAt:now.toISOString(),definitions:{realizedPl:'Payout minus stake on the settlement date. Deposits, withdrawals, transfers, credits and adjustments are excluded.',roi:'Realized betting P/L divided by non-void settled stake; null when there is no settled stake.',netCashContributed:'Starting balances plus deposits minus withdrawals. Transfers and promotional credits are excluded.',transfers:'Transfers out are recorded for source accounts only; transfers are never income or betting P/L.',calendar:'Calendar always shows the selected anchor month in the account timezone; the report totals follow the selected period.'}};
}
