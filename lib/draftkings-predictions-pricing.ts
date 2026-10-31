import Decimal from 'decimal.js';
import {createHash} from 'node:crypto';
import {ApiError} from './auth';
import {boundedFetch} from './public-nfl/sources';

export const DRAFTKINGS_FEE_URL='https://myaccount.draftkings.com/documents/fee-disclosure?product=predict';
// Published standard pricing, observed on 2026-10-31. These are fees, not market
// prices. Live use additionally verifies the official document's price bands.
export const DK_STANDARD_BANDS=[
 ['0.001','0.002','0.0000804'],['0.003','0.006','0.0002410'],
 ['0.007','0.012','0.0005610'],['0.013','0.019','0.0010380'],
 ['0.02','0.027','0.0015910'],['0.028','0.038','0.0022170'],
 ['0.039','0.052','0.0030680'],['0.053','0.071','0.0041350'],
 ['0.072','0.09','0.0055550'],['0.091','0.11','0.0069410'],
 ['0.12','0.14','0.0089930'],['0.15','0.16','0.0110340'],
 ['0.17','0.19','0.0123490'],['0.20','0.22','0.0142530'],
 ['0.23','0.26','0.0160740'],['0.27','0.29','0.0183720'],
 ['0.30','0.94','0.0200000'],['0.941','0.968','0.0105000'],
 ['0.969','0.991','0.0045000'],['0.992','0.999','0.0005000']
] as const;
export type DkFeeReference={url:string;checkedAt:string;version:string;verified:boolean};
function visibleText(html:string){return html.replace(/<script\b[^>]*>[\s\S]*?<\/script>/gi,' ').replace(/<style\b[^>]*>[\s\S]*?<\/style>/gi,' ').replace(/<[^>]*>/g,' ').replace(/&#(?:x([a-f\d]+)|(\d+));/gi,(_m,hex,decimal)=>String.fromCodePoint(parseInt(hex??decimal,hex?16:10))).replace(/&(?:nbsp|ndash|mdash|amp|dollar);/g,entity=>({'&nbsp;':' ','&ndash;':'–','&mdash;':'—','&amp;':'&','&dollar;':'$'}[entity]!)).replace(/\s+/g,' ').trim();}
export function verifyDraftKingsFeeDocument(html:string,checkedAt=new Date().toISOString()):DkFeeReference{
 const text=visibleText(html),compact=text.replace(/\s/g,'').replace(/[–—-]/g,'~');
 const bands=DK_STANDARD_BANDS.every(([low,high,fee])=>compact.includes('$'+low+'~$'+high+'$'+fee));
 const cme=text.includes('CME Markets Event Contracts:')&&text.includes('Total Fees include all applicable FCM commissions and Exchange Fees.')&&/\$0\.01\s+for contracts priced from\s+\$0\.01\s*[–—-]\s*\$0\.19/.test(text)&&/\$0\.02\s+for contracts priced from\s+\$0\.20\s*[–—-]\s*\$0\.94/.test(text)&&/\$0\.01\s+for contracts priced from\s+\$0\.95\s*[–—-]\s*\$0\.99/.test(text);
 const rounding=text.includes('rounding the transaction up on a purchase and down on a sale')&&text.includes('total of collateral and fees to a whole cent');
 return{url:DRAFTKINGS_FEE_URL,checkedAt,version:createHash('sha256').update(text).digest('hex'),verified:bands&&cme&&rounding&&text.includes('CDNA and DKeX Markets')};
}
let cached:{reference:DkFeeReference;expiresAt:number}|undefined;
export async function currentDraftKingsFeeReference():Promise<DkFeeReference>{
 if(cached&&cached.expiresAt>Date.now())return cached.reference;
 const response=await boundedFetch(DRAFTKINGS_FEE_URL,2_000_000,15000),reference=verifyDraftKingsFeeDocument(response.body.toString('utf8'));
 if(!reference.verified)throw new ApiError('Current DraftKings standard fee terms could not be matched. No fee estimate was substituted.',503);
 cached={reference,expiresAt:Date.now()+3600000};return reference;
}

/** A reference calculation for an explicitly chosen venue and standard plan.
 * It is not an invoice, a live quote, an execution or a personal transaction. */
export function draftKingsStandardFill(input:{venue:'CME'|'CDNA'|'DKeX';pricePercent:string;quantity:number;direction:'buy'|'sell'},reference:DkFeeReference){
 if(!reference.verified||reference.url!==DRAFTKINGS_FEE_URL||!Number.isFinite(Date.parse(reference.checkedAt))||Date.now()-Date.parse(reference.checkedAt)>3600000||Date.parse(reference.checkedAt)>Date.now()+60000)throw new ApiError('Freshly verified official standard fee terms are required.',503);
 if(!['CME','CDNA','DKeX'].includes(input.venue)||!['buy','sell'].includes(input.direction)||!Number.isSafeInteger(input.quantity)||input.quantity<1||input.quantity>1000000||typeof input.pricePercent!=='string'||!/^\d{1,3}(?:\.\d{1,6})?$/.test(input.pricePercent))throw new ApiError('Choose the venue, buy/sell direction, percentage price and a whole contract quantity.');
 const price=new Decimal(input.pricePercent).div(100);
 if(price.lte(0)||price.gte(1))throw new ApiError('A tradable percentage price must be greater than zero and below 100.');
 let fee:Decimal;
 if(input.venue==='CME'){
  if(!price.mul(100).isInteger()||price.lt('.01')||price.gt('.99'))throw new ApiError('The verified CME schedule covers whole-cent prices from 1% to 99%.');
  fee=new Decimal(price.lt('.20')||price.gte('.95')?'.01':'.02');
 }else{
  const band=DK_STANDARD_BANDS.find(([low,high])=>price.gte(low)&&price.lte(high));
  if(!band)throw new ApiError('This exact price falls outside the verified fee bands. No interpolation or rounding to another price was assumed.');
  fee=new Decimal(band[2]);
 }
 const collateral=price.mul(input.quantity),rawFees=fee.mul(input.quantity),unrounded=input.direction==='buy'?collateral.add(rawFees):collateral.sub(rawFees),cash=unrounded.toDecimalPlaces(2,input.direction==='buy'?Decimal.ROUND_CEIL:Decimal.ROUND_FLOOR),effective=input.direction==='buy'?cash.sub(collateral):collateral.sub(cash);
 return{kind:'standard_schedule_estimate' as const,venue:input.venue,direction:input.direction,pricePercent:new Decimal(input.pricePercent).toFixed(),quantity:input.quantity,collateralDollars:collateral.toFixed(),publishedFeePerContractDollars:fee.toFixed(),rawFeesDollars:rawFees.toFixed(),cashAmountDollars:cash.toFixed(2),cashAmountCents:cash.mul(100).toFixed(0),effectiveFeeCents:effective.mul(100).toFixed(),roundingAdjustmentDollars:effective.sub(rawFees).toFixed(),source:reference,executionVerified:false,accountPricingVerified:false,explanation:'Standard venue pricing only. Buy debits round the total collateral plus fees up to a cent; sell credits round net proceeds down. The account, venue, actual fills and settlement terms must be independently verified. This calculation neither places nor records a transaction.'};
}
