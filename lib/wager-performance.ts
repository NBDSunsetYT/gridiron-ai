import Decimal from 'decimal.js';
const ExactDecimal=Decimal.clone({precision:50});

type Wager=Record<string,any>;
export type RecordedWagerSport='NFL'|'CFB'|'Unspecified';
export type WagerFilters={sport?:RecordedWagerSport|'all';sportsbook?:string;market?:string;from?:string;to?:string};
/** Missing historical metadata stays unspecified, regardless of event text. */
export function recordedWagerSport(wager:Wager):RecordedWagerSport{return wager.sport==='NFL'||wager.sport==='CFB'?wager.sport:'Unspecified';}
function dateBoundary(value:string|undefined,next=false){
 if(!value)return null;
 if(!/^\d{4}-\d{2}-\d{2}$/.test(value))return NaN;
 const [year,month,day]=value.split('-').map(Number),date=new Date(year,month-1,day);
 if(date.getFullYear()!==year||date.getMonth()!==month-1||date.getDate()!==day)return NaN;
 if(next)date.setDate(date.getDate()+1);
 return date.getTime();
}
/** Settled results use settlement dates; open stakes use placement dates.
 * Browser-local day bounds follow local DST, rather than adding 24 hours. */
export function filterRecordedWagers<T extends Wager>(wagers:T[],filters:WagerFilters={}):T[]{
 const from=dateBoundary(filters.from),to=dateBoundary(filters.to,true);
 return wagers.filter(wager=>{
  if(filters.sport&&filters.sport!=='all'&&recordedWagerSport(wager)!==filters.sport)return false;
  if(filters.sportsbook&&filters.sportsbook!=='all'&&wager.sportsbook!==filters.sportsbook)return false;
  if(filters.market&&filters.market!=='all'&&wager.market!==filters.market)return false;
  if(from!==null||to!==null){const at=Date.parse((wager.result??wager.status)==='pending'?wager.placedAt:wager.settledAt);if(!Number.isFinite(at)||from!==null&&(!Number.isFinite(from)||at<from)||to!==null&&(!Number.isFinite(to)||at>=to))return false;}
  return true;
 });
}
function exactCents(row:Wager,key:'stake'|'payout'){
 const cents=row[`${key}Cents`];
 if(typeof cents==='number'&&!Number.isSafeInteger(cents))throw Error('Recorded performance requires exact whole cents.');
 const value=cents!==undefined&&cents!==null?new ExactDecimal(cents):row[key]!==undefined&&row[key]!==null?new ExactDecimal(row[key]).mul(100):null;
 if(value===null||!value.isFinite()||!value.isInteger()||value.isNegative())throw Error('A recorded settlement is missing an exact nonnegative amount.');
 return value;
}
/** View-only totals. No journal entries or account balances are changed.
 * Matches the ledger ROI definition: actual net P/L including void fees,
 * divided by non-void settled stake. Capital movements never enter this input. */
export function recordedWagerPerformance(wagers:Wager[]){
 let profit=new ExactDecimal(0),stake=new ExactDecimal(0),pending=new ExactDecimal(0),settled=0,voided=0,incomplete=0;
 for(const wager of wagers){
  const result=wager.result??wager.status;
  try{
   if(result==='pending'){pending=pending.add(exactCents(wager,'stake'));continue;}
   if(!['won','lost','voided','cashed_out'].includes(result))throw Error('Unknown recorded settlement.');
   const cost=exactCents(wager,'stake'),payout=exactCents(wager,'payout');
   profit=profit.add(payout.sub(cost));settled++;
   if(result==='voided')voided++;else stake=stake.add(cost);
  }catch{incomplete++;}
 }
 return{wagers:wagers.length,settledBets:settled,voidedBets:voided,incompleteRecords:incomplete,realizedPlCents:incomplete?null:profit.toFixed(0),settledStakeCents:incomplete?null:stake.toFixed(0),pendingExposureCents:incomplete?null:pending.toFixed(0),roi:!incomplete&&stake.gt(0)?profit.div(stake).toFixed():null};
}
