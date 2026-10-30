import Decimal from 'decimal.js';
import { randomUUID } from 'node:crypto';
import { getDb } from './db';
import { ApiError } from './auth';
export const SPORTSBOOKS = ['DraftKings','Hard Rock'] as const;
const MAX_CENTS = 100_000_000_000;
export function moneyToCents(input: string | number): number {
  const text=String(input);
  if (!/^-?\d+(\.\d{1,2})?$/.test(text)) throw new ApiError('Amounts must have at most two decimal places.');
  const decimal=new Decimal(text).times(100);
  if (!decimal.isInteger() || !decimal.isFinite() || decimal.abs().gt(MAX_CENTS)) throw new ApiError('Amount is outside the supported range.');
  return decimal.toNumber();
}
export function centsToMoney(cents:number): string {return new Decimal(cents).div(100).toFixed(2);}
function sportsbook(input:unknown): string {if (!SPORTSBOOKS.includes(input as typeof SPORTSBOOKS[number])) throw new ApiError('Choose DraftKings or Hard Rock.'); return input as string;}
function dateString(value:unknown):string {
  if (value===undefined || value==='') return new Date().toISOString();
  const date=new Date(String(value)); if (!Number.isFinite(date.getTime())) throw new ApiError('Choose a valid date and time.');
  if (date.getTime()>Date.now()+60_000) throw new ApiError('Recorded transactions cannot be in the future.');
  return date.toISOString();
}
function textValue(value:unknown,max=2000):string {if (value===undefined || value===null) return ''; if (typeof value!=='string'||value.length>max) throw new ApiError('Invalid text field.');return value.trim();}
function balance(userId:string,book:string,account='cash'):number {
  const row=getDb().prepare('SELECT COALESCE(SUM(p.amount_cents),0) AS balance FROM postings p JOIN journal j ON j.id=p.journal_id WHERE j.user_id=? AND p.sportsbook=? AND p.account=?').get(userId,book,account) as {balance:number};return row.balance;
}
type Posting={account:string;sportsbook:string;amount:number};
type JournalInput={type:string;sportsbook:string;amount:number;date:string;note?:string;reference?:string;relatedId?:string;reversesId?:string};
function writeJournal(userId:string,input:JournalInput,postings:Posting[]) {
  if (postings.reduce((sum,p)=>sum+p.amount,0)!==0) throw new Error('Unbalanced journal rejected.');
  if (!postings.every(p=>Number.isSafeInteger(p.amount))) throw new Error('Non-integer journal amount rejected.');
  const db=getDb();const id=randomUUID(); const now=new Date().toISOString();
  for(const p of postings){const current=balance(userId,p.sportsbook,p.account);if(!Number.isSafeInteger(current+p.amount))throw new ApiError('Account balance exceeds the supported exact-arithmetic range.');}
  db.prepare('INSERT INTO journal(id,user_id,type,sportsbook,amount_cents,date,note,reference,related_id,reverses_id,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)').run(id,userId,input.type,input.sportsbook,input.amount,input.date,input.note||'',input.reference||null,input.relatedId||null,input.reversesId||null,now);
  const insert=db.prepare('INSERT INTO postings(journal_id,account,sportsbook,amount_cents) VALUES(?,?,?,?)');
  for (const p of postings) insert.run(id,p.account,p.sportsbook,p.amount);
  db.prepare('INSERT INTO audit(user_id,action,entity_id,detail,created_at) VALUES(?,?,?,?,?)').run(userId,input.reversesId?'reverse':'create',id,JSON.stringify(input),now);
  return {id,...input,amountCents:input.amount,amount:centsToMoney(input.amount)};
}
function checkAvailable(userId:string,book:string,cents:number) {if (balance(userId,book)<cents) throw new ApiError('Insufficient available balance. Record a deposit or starting balance first.');}
export function postTransaction(userId:string,input:Record<string,unknown>) {
  return getDb().transaction(()=>{
    const book=sportsbook(input.sportsbook); const type=String(input.type); const cents=moneyToCents(input.amount as string);
    if (!['starting_balance','deposit','withdrawal','transfer','promotional_credit','adjustment','refund'].includes(type)) throw new ApiError('Unsupported transaction type. Record wagers and settlements in Bet History.');
    if (cents===0 || (type!=='adjustment'&&cents<0)) throw new ApiError('Amount must be greater than zero.');
    const date=dateString(input.date);const note=textValue(input.note);const reference=textValue(input.reference,200);
    if (type==='starting_balance' && getDb().prepare("SELECT id FROM journal WHERE user_id=? AND sportsbook=? AND type='starting_balance' AND id NOT IN (SELECT reverses_id FROM journal WHERE reverses_id IS NOT NULL)").get(userId,book)) throw new ApiError('A starting balance already exists for this sportsbook. Use a deposit or adjustment.');
    if (type==='transfer') {
      const target=sportsbook(input.toSportsbook); if(target===book) throw new ApiError('Choose a different destination sportsbook.');checkAvailable(userId,book,cents);
      return writeJournal(userId,{type,sportsbook:book,amount:cents,date,note:note||`Transfer to ${target}`,reference},[{account:'cash',sportsbook:book,amount:-cents},{account:'cash',sportsbook:target,amount:cents}]);
    }
    const sign=type==='withdrawal'?-1:1;const delta=cents*sign;if(delta<0)checkAvailable(userId,book,-delta);
    const category=type==='promotional_credit'?'promotion':type==='adjustment'||type==='refund'?'adjustment':'capital';
    return writeJournal(userId,{type,sportsbook:book,amount:cents,date,note,reference},[{account:'cash',sportsbook:book,amount:delta},{account:category,sportsbook:book,amount:-delta}]);
  })();
}
export function reverseTransaction(userId:string,id:string,note:string) {
  return getDb().transaction(()=>{
    const db=getDb();const entry=db.prepare('SELECT * FROM journal WHERE id=? AND user_id=?').get(id,userId) as Record<string,any>|undefined;
    if(!entry)throw new ApiError('Transaction not found.',404);
    if(['wager','settlement','reversal'].includes(entry.type))throw new ApiError('Wager and settlement records cannot be reversed here.');
    if(db.prepare('SELECT id FROM journal WHERE reverses_id=?').get(id))throw new ApiError('This transaction has already been reversed.',409);
    const postings=db.prepare('SELECT account,sportsbook,amount_cents FROM postings WHERE journal_id=?').all(id) as {account:string;sportsbook:string;amount_cents:number}[];
    for(const p of postings)if(p.account==='cash'&&p.amount_cents>0)checkAvailable(userId,p.sportsbook,p.amount_cents);
    return writeJournal(userId,{type:'reversal',sportsbook:entry.sportsbook,amount:-entry.amount_cents,date:new Date().toISOString(),note:textValue(note)||'Correction reversal',reversesId:id},postings.map(p=>({account:p.account,sportsbook:p.sportsbook,amount:-p.amount_cents})));
  })();
}
export function placeBet(userId:string,input:Record<string,unknown>) {
  return getDb().transaction(()=>{
    const db=getDb(); const book=sportsbook(input.sportsbook); const cents=moneyToCents(input.stake as string);
    if(cents<=0)throw new ApiError('Stake must be greater than zero.');checkAvailable(userId,book,cents);
    const odds=Number(input.odds);if(!Number.isInteger(odds)||Math.abs(odds)<100||Math.abs(odds)>100_000)throw new ApiError('Enter valid American odds: -100 or less, or +100 or more.');
    const event=textValue(input.event,300),market=textValue(input.market,200),selection=textValue(input.selection,500);
    if(!event||!market||!selection)throw new ApiError('Event, market, and selection are required.');
    const placedAt=dateString(input.placementTime||input.placedAt||input.date);
    const setting=db.prepare('SELECT monthly_limit_cents FROM settings WHERE user_id=?').get(userId) as {monthly_limit_cents:number|null}|undefined;
    if(setting?.monthly_limit_cents!==null&&setting?.monthly_limit_cents!==undefined) {
      const timezone=getSettings(userId).timezone;
      const monthOf=(value:string)=>new Intl.DateTimeFormat('en-US',{timeZone:timezone,year:'numeric',month:'2-digit'}).format(new Date(value));
      const month=monthOf(placedAt);
      const previous=db.prepare('SELECT stake_cents,placed_at FROM bets WHERE user_id=?').all(userId) as {stake_cents:number;placed_at:string}[];
      const spent=previous.filter(b=>monthOf(b.placed_at)===month).reduce((sum,b)=>sum+b.stake_cents,0);
      if(spent+cents>setting.monthly_limit_cents)throw new ApiError('This wager exceeds your configured monthly stake limit.');
    }
    if(input.legs!==undefined&&(!Array.isArray(input.legs)||input.legs.length<2||input.legs.length>12))throw new ApiError('Parlays must contain 2–12 legs.');
    const prediction=input.prediction===undefined?null:JSON.stringify(input.prediction);if(prediction&&prediction.length>50_000)throw new ApiError('Prediction snapshot is too large.');
    const id=randomUUID();const now=new Date().toISOString();
    db.prepare('INSERT INTO bets(id,user_id,sportsbook,event,market,selection,odds,stake_cents,placed_at,notes,prediction,legs,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)').run(id,userId,book,event,market,selection,odds,cents,placedAt,textValue(input.notes),prediction,input.legs?JSON.stringify(input.legs):null,now);
    writeJournal(userId,{type:'wager',sportsbook:book,amount:cents,date:placedAt,note:selection,relatedId:id},[{account:'cash',sportsbook:book,amount:-cents},{account:'escrow',sportsbook:book,amount:cents}]);
    return {id,result:'pending',stakeCents:cents,stake:centsToMoney(cents)};
  })();
}
export function settleBet(userId:string,input:Record<string,unknown>) {
  return getDb().transaction(()=>{
    const db=getDb();const bet=db.prepare('SELECT * FROM bets WHERE id=? AND user_id=?').get(String(input.id),userId) as Record<string,any>|undefined;
    if(!bet)throw new ApiError('Wager not found.',404);if(bet.result!=='pending')throw new ApiError('This wager has already been settled.',409);
    const result=String(input.result);if(!['won','lost','voided','cashed_out'].includes(result))throw new ApiError('Choose a valid settlement result.');
    let payout:number;
    if(result==='lost'){if(input.payout!==undefined&&input.payout!==''&&moneyToCents(input.payout as string)!==0)throw new ApiError('A lost wager has a zero payout. Use cash-out for a partial return.');payout=0;}
    else if(result==='voided'){if(input.payout!==undefined&&input.payout!==''&&moneyToCents(input.payout as string)!==bet.stake_cents)throw new ApiError('A voided wager must return exactly the stake.');payout=bet.stake_cents;}
    else if(input.payout!==undefined&&input.payout!=='')payout=moneyToCents(input.payout as string);
    else if(result==='cashed_out')throw new ApiError('Enter the actual cash-out payout including any returned stake.');
    else {const multiplier=bet.odds>0?new Decimal(bet.odds).div(100):new Decimal(100).div(-bet.odds);payout=new Decimal(bet.stake_cents).times(multiplier.plus(1)).toDecimalPlaces(0,Decimal.ROUND_HALF_UP).toNumber();}
    if(payout<0||payout>MAX_CENTS)throw new ApiError('Payout is outside the supported range.');
    if(result==='won'&&payout<bet.stake_cents)throw new ApiError('A winning payout must include the returned stake. Use cash-out for a partial return.');
    const settledAt=dateString(input.settlementTime||input.settledAt||input.date);if(settledAt<bet.placed_at)throw new ApiError('Settlement cannot precede placement.');
    db.prepare('UPDATE bets SET result=?,payout_cents=?,settled_at=? WHERE id=?').run(result,payout,settledAt,bet.id);
    writeJournal(userId,{type:'settlement',sportsbook:bet.sportsbook,amount:payout,date:settledAt,note:result,relatedId:bet.id},[{account:'escrow',sportsbook:bet.sportsbook,amount:-bet.stake_cents},{account:'cash',sportsbook:bet.sportsbook,amount:payout},{account:'betting_pnl',sportsbook:bet.sportsbook,amount:bet.stake_cents-payout}]);
    return {id:bet.id,result,payoutCents:payout,payout:centsToMoney(payout),profitCents:payout-bet.stake_cents};
  })();
}
export function updateSettings(userId:string,input:Record<string,unknown>) {
  const db=getDb();db.prepare('INSERT OR IGNORE INTO settings(user_id) VALUES(?)').run(userId);
  if('monthlyLimitCents' in input){const limit=input.monthlyLimitCents;if(limit!==null&&(!Number.isSafeInteger(limit)||(limit as number)<0||(limit as number)>MAX_CENTS))throw new ApiError('Monthly stake limit must be a nonnegative number of cents or null.');db.prepare('UPDATE settings SET monthly_limit_cents=? WHERE user_id=?').run(limit,userId);}
  if('timezone' in input){try{new Intl.DateTimeFormat('en',{timeZone:String(input.timezone)}).format();}catch{throw new ApiError('Choose a valid timezone.');}db.prepare('UPDATE settings SET timezone=? WHERE user_id=?').run(String(input.timezone),userId);}
  if('theme' in input){if(!['dark','light','system'].includes(String(input.theme)))throw new ApiError('Invalid theme.');db.prepare('UPDATE settings SET theme=? WHERE user_id=?').run(String(input.theme),userId);}
  if('notifications' in input){if(!input.notifications||typeof input.notifications!=='object'||Array.isArray(input.notifications)||Object.keys(input.notifications).length>30||!Object.values(input.notifications).every(v=>typeof v==='boolean'))throw new ApiError('Invalid notification preferences.');db.prepare('UPDATE settings SET notifications=? WHERE user_id=?').run(JSON.stringify(input.notifications),userId);}
  return getSettings(userId);
}
export function getSettings(userId:string){const s=getDb().prepare('SELECT * FROM settings WHERE user_id=?').get(userId) as Record<string,any>|undefined;return{monthlyLimitCents:s?.monthly_limit_cents??null,timezone:s?.timezone||'UTC',notifications:JSON.parse(s?.notifications||'{}'),theme:s?.theme||'dark'};}
export function getLedger(userId:string) {
  const db=getDb();const accounts=SPORTSBOOKS.map(book=>{const available=balance(userId,book);const pending=balance(userId,book,'escrow');return{sportsbook:book,cashBalanceCents:available+pending,availableBalanceCents:available,pendingExposureCents:pending,balance:centsToMoney(available+pending)};});
  const raw=db.prepare('SELECT * FROM journal WHERE user_id=? ORDER BY date DESC,created_at DESC').all(userId) as Record<string,any>[];
  const transactions=raw.map(t=>({id:t.id,type:t.type,sportsbook:t.sportsbook,amountCents:t.amount_cents,amount:centsToMoney(t.amount_cents),date:t.date,note:t.note,reference:t.reference,relatedId:t.related_id,reversesId:t.reverses_id,createdAt:t.created_at,reversed:raw.some(r=>r.reverses_id===t.id)}));
  const rawBets=db.prepare('SELECT * FROM bets WHERE user_id=? ORDER BY placed_at DESC').all(userId) as Record<string,any>[];
  const bets=rawBets.map(b=>({id:b.id,sportsbook:b.sportsbook,event:b.event,market:b.market,selection:b.selection,odds:b.odds,stakeCents:b.stake_cents,stake:centsToMoney(b.stake_cents),placedAt:b.placed_at,settledAt:b.settled_at,result:b.result,payoutCents:b.payout_cents,payout:b.payout_cents===null?null:centsToMoney(b.payout_cents),notes:b.notes,prediction:b.prediction?JSON.parse(b.prediction):null,legs:b.legs?JSON.parse(b.legs):null}));
  const active=transactions.filter(t=>!t.reversed&&t.type!=='reversal');const sumType=(type:string)=>active.filter(t=>t.type===type).reduce((s,t)=>s+t.amountCents,0);
  const settled=bets.filter(b=>b.result!=='pending');const nonvoid=settled.filter(b=>b.result!=='voided');const settledStake=nonvoid.reduce((s,b)=>s+b.stakeCents,0);const profits=settled.map(b=>(b.payoutCents??0)-b.stakeCents);const realized=profits.reduce((s,v)=>s+v,0);
  const summary={cashBalanceCents:accounts.reduce((s,a)=>s+a.cashBalanceCents,0),availableBalanceCents:accounts.reduce((s,a)=>s+a.availableBalanceCents,0),pendingExposureCents:accounts.reduce((s,a)=>s+a.pendingExposureCents,0),realizedPlCents:realized,totalDepositsCents:sumType('deposit'),totalWithdrawalsCents:sumType('withdrawal'),netCashContributedCents:sumType('starting_balance')+sumType('deposit')-sumType('withdrawal'),settledStakeCents:settledStake,roi:settledStake?realized/settledStake:null,averageStakeCents:bets.length?Math.round(bets.reduce((s,b)=>s+b.stakeCents,0)/bets.length):0,largestWinCents:Math.max(0,...profits),largestLossCents:Math.min(0,...profits),totalBets:bets.length,settledBets:settled.length};
  const series=new Map<string,{profitCents:number;balanceCents:number}>();let runningBalance=0,runningProfit=0;
  for(const t of [...raw].reverse()){
    const postings=db.prepare('SELECT account,amount_cents FROM postings WHERE journal_id=?').all(t.id) as {account:string;amount_cents:number}[];
    runningBalance+=postings.filter(p=>p.account==='cash'||p.account==='escrow').reduce((s,p)=>s+p.amount_cents,0);runningProfit-=postings.filter(p=>p.account==='betting_pnl').reduce((s,p)=>s+p.amount_cents,0);
    series.set(t.date.slice(0,10),{profitCents:runningProfit,balanceCents:runningBalance});
  }
  const chart=Array.from(series,([date,values])=>({date,...values}));
  const audit=db.prepare('SELECT action,entity_id AS entityId,detail,created_at AS createdAt FROM audit WHERE user_id=? ORDER BY id DESC LIMIT 200').all(userId);
  const performanceByMarket=Array.from(new Set(nonvoid.map(b=>b.market)),market=>{const group=nonvoid.filter(b=>b.market===market);const stakeCents=group.reduce((s,b)=>s+b.stakeCents,0);const profitCents=group.reduce((s,b)=>s+(b.payoutCents??0)-b.stakeCents,0);return {market,bets:group.length,stakeCents,profitCents,roi:stakeCents?profitCents/stakeCents:null};});
  const performanceBySportsbook=SPORTSBOOKS.map(sportsbook=>{const group=nonvoid.filter(b=>b.sportsbook===sportsbook);const stakeCents=group.reduce((s,b)=>s+b.stakeCents,0);const profitCents=group.reduce((s,b)=>s+(b.payoutCents??0)-b.stakeCents,0);return {sportsbook,bets:group.length,stakeCents,profitCents,roi:stakeCents?profitCents/stakeCents:null};});
  return {accounts,transactions,summary,chart,bets,audit,performanceByMarket,performanceBySportsbook};
}
