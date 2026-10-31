import Decimal from 'decimal.js';
import {ApiError} from './auth';

/** Financial records describe actual manual fills; quotes never become wagers. */
export type WagerMetadata={marketInstrument:'sportsbook'|'event_contract';player:string|null;odds:number|null;contractPriceCents:string|null;contractQuantity:number|null;entryFeeCents:string|null};
export function wagerMetadata(input:Record<string,unknown>,stakeCents:number):WagerMetadata{
 if(!Number.isSafeInteger(stakeCents)||stakeCents<=0)throw new ApiError('Actual stake must be a positive exact amount in cents.');
 const instrument=input.marketInstrument??'sportsbook';
 if(instrument!=='sportsbook'&&instrument!=='event_contract')throw new ApiError('Choose a sportsbook wager or an event contract.');
 if(input.player!==undefined&&input.player!==null&&(typeof input.player!=='string'||input.player.length>180))throw new ApiError('Player must be text of at most 180 characters.');
 const player=typeof input.player==='string'?input.player.trim()||null:null;
 if(instrument==='sportsbook'){
  const odds=Number(input.odds);
  if(!Number.isInteger(odds)||Math.abs(odds)<100||Math.abs(odds)>100_000)throw new ApiError('Enter valid American odds: -100 or less, or +100 or more.');
  if(['contractPriceCents','contractQuantity','entryFeeCents'].some(k=>input[k]!==undefined&&input[k]!==null&&input[k]!==''))throw new ApiError('Event-contract prices and fees belong to an event-contract record.');
  return{marketInstrument:instrument,player,odds,contractPriceCents:null,contractQuantity:null,entryFeeCents:null};
 }
 if(input.odds!==undefined&&input.odds!==null&&input.odds!=='')throw new ApiError('Record an event-contract price without American odds.');
 if(typeof input.contractPriceCents!=='string'||!/^\d{1,3}(?:\.\d{1,6})?$/.test(input.contractPriceCents))throw new ApiError('Enter the actual contract fill price in cents, with at most six decimal places.');
 const price=new Decimal(input.contractPriceCents);
 if(price.lte(0)||price.gt(100))throw new ApiError('Contract fill price must be greater than zero and at most 100 cents.');
 const suppliedQuantity=input.contractQuantity!==undefined&&input.contractQuantity!==null&&input.contractQuantity!=='';
 const quantity=suppliedQuantity?input.contractQuantity:null;
 if(quantity!==null&&(!Number.isInteger(quantity)||(quantity as number)<1||(quantity as number)>1_000_000))throw new ApiError('Contract quantity must be a whole number from 1 to 1,000,000.');
 const suppliedFee=input.entryFeeCents!==undefined&&input.entryFeeCents!==null&&input.entryFeeCents!=='';
 if(suppliedFee&&(typeof input.entryFeeCents!=='string'||!/^\d{1,12}(?:\.\d{1,6})?$/.test(input.entryFeeCents)))throw new ApiError('Enter the actual total entry fee in cents, with at most six decimal places.');
 const fee=suppliedFee?new Decimal(input.entryFeeCents as string):null;
 if(fee&&fee.gt(stakeCents))throw new ApiError('Entry fees cannot exceed the total amount debited.');
 if(quantity!==null){
  if(!fee)throw new ApiError('Enter the actual total entry fee when recording contract quantity.');
  if(!price.mul(quantity as number).add(fee).eq(stakeCents))throw new ApiError('Actual total stake must equal fill price × quantity plus the total entry fee. Do not estimate a rounded fill.');
 }
 return{marketInstrument:instrument,player,odds:null,contractPriceCents:price.toFixed(),contractQuantity:quantity as number|null,entryFeeCents:fee?.toFixed()??null};
}
