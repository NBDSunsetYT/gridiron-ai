import Decimal from 'decimal.js';
export const PROP_SORTS={probability:'Highest GRIDIRON AI probability',value:'Highest estimated net value after costs',difference:'Largest model–market difference',uncertainty:'Lowest quantified model uncertainty',updated:'Most recently updated',kickoff:'Kickoff time',player:'Player name'} as const;
export type PropSort=keyof typeof PROP_SORTS;
export type PropView={sort:PropSort;game:string;grouped:boolean;layout?:'cards'|'board';favorites?:string[];favoritesOnly?:boolean};
export const DEFAULT_PROP_VIEW:PropView={sort:'probability',game:'all',grouped:false};
export function validPropView(value:any):PropView|null{
 if(!value||!Object.hasOwn(PROP_SORTS,value.sort)||typeof value.game!=='string'||value.game.length>=180||typeof value.grouped!=='boolean')return null;
 const result:PropView={sort:value.sort,game:value.game,grouped:value.grouped};
 if(['cards','board'].includes(value.layout))result.layout=value.layout;
 if(Array.isArray(value.favorites)&&value.favorites.length<=100&&value.favorites.every((s:any)=>typeof s==='string'&&s.length<=1200))result.favorites=[...new Set<string>(value.favorites)];
 if(typeof value.favoritesOnly==='boolean')result.favoritesOnly=value.favoritesOnly;
 return result;
}
export const estimatedProbability=(row:any):number|null=>{const p=row.calibratedProbability??row.estimateProbability??row.posteriorProbability??row.modelProbability??row.empiricalProbability;return typeof p==='number'&&Number.isFinite(p)&&p>=0&&p<=1?p:null;};
export type QuotePrice={family:'sportsbook';americanOdds?:number;decimalOdds?:string|number}|{family:'event_contract';acquisitionCost:string;payout:string;entryFee:string|null;winningFee:string|null;settlementVerified:boolean};
/** Event acquisition/payout/fees use the same currency and actual per-unit terms.
 * Displayed percentages/multipliers alone do not establish any of those terms. */
export function priceProbabilities(quote:QuotePrice){
 const empty={beforeFees:null as number|null,afterFees:null as number|null,decimalOdds:null as string|null,feesVerified:false};
 try{
  if(quote.family==='sportsbook'){
   let dec:Decimal;if(quote.decimalOdds!==undefined)dec=new Decimal(quote.decimalOdds);else{const a=quote.americanOdds;if(!Number.isFinite(a)||!Number.isInteger(a)||Math.abs(a!)<100)return empty;dec=new Decimal(a!).gt(0)?new Decimal(a!).div(100).plus(1):new Decimal(100).div(Math.abs(a!)).plus(1);}
   if(!dec.isFinite()||dec.lte(1))return empty;return{...empty,beforeFees:new Decimal(1).div(dec).toNumber(),decimalOdds:dec.toString()};
  }
  if(!quote.settlementVerified)return empty;
  const cost=new Decimal(quote.acquisitionCost),payout=new Decimal(quote.payout);if(!cost.isFinite()||!payout.isFinite()||cost.lte(0)||payout.lte(0)||cost.gte(payout))return empty;
  const beforeFees=cost.div(payout).toNumber();if(quote.entryFee===null||quote.winningFee===null)return{...empty,beforeFees};
  const entry=new Decimal(quote.entryFee),win=new Decimal(quote.winningFee);if(!entry.isFinite()||!win.isFinite()||entry.lt(0)||win.lt(0)||win.gte(payout))return{...empty,beforeFees};
  return{...empty,beforeFees,afterFees:cost.plus(entry).div(payout.minus(win)).toNumber(),feesVerified:true};
 }catch{return empty;}
}
export function marketComparison(row:any,now=Date.now()){
 const at=Date.parse(row.sourceUpdatedAt??''),fresh=row.marketCurrent!==false&&Number.isFinite(at)&&at<=now+60000&&now-at<=300000;
 // Only an explicit product-family discriminator is trusted. Book names cannot
 // turn sportsbook odds into percentage-priced event contracts.
 const event=row.dataFamily==='event_contract',sportsbook=row.dataFamily==='sportsbook_reference'||row.dataFamily===undefined&&Number.isFinite(row.americanOdds);
 const quote=event&&row.priceTerms?priceProbabilities({family:'event_contract',...row.priceTerms}):sportsbook?priceProbabilities({family:'sportsbook',americanOdds:row.americanOdds,decimalOdds:row.decimalOdds}):null;
 const beforeFees=fresh?quote?.beforeFees??null:null,afterFees=fresh?quote?.afterFees??null:null,p=estimatedProbability(row),difference=p!==null&&beforeFees!==null&&!row.stale&&Date.parse(row.kickoff)>now?(p-beforeFees)*100:null;
 return{beforeFees,afterFees,differencePp:difference,decimalOdds:quote?.decimalOdds??null,family:event?'event_contract':sportsbook?'sportsbook_reference':'unknown',current:fresh,feesVerified:quote?.feesVerified??false,reason:!fresh?'Current market comparison unavailable; quote is missing or stale.':quote?.beforeFees===null?'Verified price and payout terms unavailable.':'Descriptive percentage-point difference; incomplete settlement, fees and model validation do not establish positive net value.'};
}
export function thresholdKey(value:unknown){try{return new Decimal(String(value)).toString();}catch{return String(value);}}
export const propGameKey=(row:any)=>row.sport+':'+(row.espnEventId?'espn:'+row.espnEventId:'provider:'+row.eventId);
export function localDay(at:number,timezone:string){return new Intl.DateTimeFormat('en-CA',{timeZone:timezone,year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date(at));}
export function tomorrowDay(today:string){const [y,m,d]=today.split('-').map(Number);return new Date(Date.UTC(y,m-1,d+1)).toISOString().slice(0,10);}
export function viewProps(items:any[],view:PropView,options:{category?:string;book?:string;now?:number;timezone?:string}={}){
 const now=options.now??Date.now(),timezone=options.timezone??'America/New_York',today=localDay(now,timezone),tomorrow=tomorrowDay(today);
 const rows=items.filter(row=>(!options.category||options.category==='all'||row.market===options.category)&&(!options.book||options.book==='all'||row.book.key===options.book)&&(()=>{const at=Date.parse(row.kickoff);if(view.game==='all')return true;if(!Number.isFinite(at))return false;if(view.game==='today')return localDay(at,timezone)===today;if(view.game==='tomorrow')return localDay(at,timezone)===tomorrow;if(view.game==='upcoming')return at>now;return propGameKey(row)===view.game;})());
 const ready=(r:any)=>estimatedProbability(r)!==null&&!r.stale&&r.state!=='source_unavailable'&&Date.parse(r.kickoff)>now;
 const quantifiedWidth=(r:any)=>Array.isArray(r.modelInterval95)&&r.modelInterval95.length===2&&r.modelInterval95.every(Number.isFinite)?r.modelInterval95[1]-r.modelInterval95[0]:null;
 const value=(r:any)=>r.feesVerified===true&&r.settlementVerified===true&&typeof r.expectedNetRoi==='number'&&Number.isFinite(r.expectedNetRoi)?r.expectedNetRoi:null;
 const compare=(a:number|null,b:number|null,direction=1)=>a===null&&b===null?0:a===null?1:b===null?-1:direction*(a-b);
 return rows.sort((a,b)=>{const complete=Number(ready(b))-Number(ready(a));if(complete)return complete;let order=0;
  switch(view.sort){case'value':order=compare(value(a),value(b),-1);break;case'difference':order=compare(marketComparison(a,now).differencePp,marketComparison(b,now).differencePp,-1);break;case'uncertainty':order=compare(quantifiedWidth(a),quantifiedWidth(b));break;case'updated':order=compare(Number.isFinite(Date.parse(a.calculatedAt))?Date.parse(a.calculatedAt):null,Number.isFinite(Date.parse(b.calculatedAt))?Date.parse(b.calculatedAt):null,-1);break;case'kickoff':order=Date.parse(a.kickoff)-Date.parse(b.kickoff);break;case'player':order=String(a.player.name).localeCompare(String(b.player.name));break;default:order=compare(estimatedProbability(a),estimatedProbability(b),-1);}
  return order||compare(estimatedProbability(a),estimatedProbability(b),-1)||String(a.player.name).localeCompare(String(b.player.name))||String(a.id).localeCompare(String(b.id));
 });
}
