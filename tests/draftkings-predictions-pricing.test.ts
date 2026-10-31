import {describe,it,expect,vi,afterEach} from 'vitest';
import {DK_STANDARD_BANDS,DRAFTKINGS_FEE_URL,verifyDraftKingsFeeDocument,draftKingsStandardFill} from '../lib/draftkings-predictions-pricing';
// SYNTHETIC document formatting around the published fee bands. No live price,
// fill, account fee or prediction is represented by these arithmetic inputs.
const document=()=>`<h1>CDNA and DKeX Markets</h1><table>${DK_STANDARD_BANDS.map(([low,high,fee])=>`<tr><td>$${low} &ndash; $${high}</td><td>$${fee}</td></tr>`).join('')}</table><p>The total of collateral and fees to a whole cent, rounding the transaction up on a purchase and down on a sale.</p><h2>CME Markets Event Contracts:</h2><p>Total Fees: $0.01 for contracts priced from $0.01 – $0.19; $0.02 for contracts priced from $0.20 – $0.94; $0.01 for contracts priced from $0.95 – $0.99. Total Fees include all applicable FCM commissions and Exchange Fees.</p>`;
const reference=()=>verifyDraftKingsFeeDocument(document());
afterEach(()=>vi.useRealTimers());
describe('DraftKings Predictions standard venue fees and cash rounding',()=>{
 it('requires all official venue bands and rounding rules instead of assuming a flat broker fee',()=>{
  expect(reference().verified).toBe(true);
  expect(verifyDraftKingsFeeDocument(document().replace('0.0142530','0.0152530')).verified).toBe(false);
  expect(verifyDraftKingsFeeDocument(document().replace('Total Fees include all applicable FCM commissions and Exchange Fees.','')).verified).toBe(false);
  expect(()=>draftKingsStandardFill({venue:'CME',pricePercent:'40',quantity:100,direction:'buy'},{...reference(),verified:false})).toThrow(/verified official/);
 });
 it('charges the venue-specific CME total fee at every price boundary',()=>{
  for(const[price,fee]of[['1','.01'],['19','.01'],['20','.02'],['94','.02'],['95','.01'],['99','.01']])expect(draftKingsStandardFill({venue:'CME',pricePercent:price,quantity:1,direction:'buy'},reference()).publishedFeePerContractDollars).toBe(Number(fee).toString());
  expect(draftKingsStandardFill({venue:'CME',pricePercent:'40',quantity:100,direction:'buy'},reference())).toMatchObject({cashAmountCents:'4200',effectiveFeeCents:'200',executionVerified:false,accountPricingVerified:false});
 });
 it('rounds a fractional-price CDNA purchase total rather than separately rounding fees',()=>{
  expect(draftKingsStandardFill({venue:'CDNA',pricePercent:'0.1',quantity:1,direction:'buy'},reference())).toMatchObject({collateralDollars:'0.001',rawFeesDollars:'0.0000804',cashAmountCents:'1',effectiveFeeCents:'0.9'});
  // Incorrect ceil(fee)+collateral would debit 1.1 cents, an impossible cash debit.
  expect(draftKingsStandardFill({venue:'CDNA',pricePercent:'0.1',quantity:100,direction:'buy'},reference())).toMatchObject({cashAmountCents:'11',effectiveFeeCents:'1'});
 });
 it('rounds actual net sale credits down and retains the transaction rounding adjustment',()=>{
  expect(draftKingsStandardFill({venue:'DKeX',pricePercent:'50',quantity:1,direction:'sell'},reference())).toMatchObject({cashAmountCents:'48',effectiveFeeCents:'2'});
  expect(draftKingsStandardFill({venue:'CDNA',pricePercent:'0.1',quantity:1,direction:'sell'},reference())).toMatchObject({cashAmountCents:'0',effectiveFeeCents:'0.1'});
 });
 it('withholds fee-band gaps and unsupported CME fractional ticks without interpolation',()=>{
  expect(()=>draftKingsStandardFill({venue:'CDNA',pricePercent:'11.5',quantity:1,direction:'buy'},reference())).toThrow(/outside the verified fee bands/);
  expect(()=>draftKingsStandardFill({venue:'CME',pricePercent:'40.1',quantity:1,direction:'buy'},reference())).toThrow(/whole-cent/);
  expect(()=>draftKingsStandardFill({venue:'CDNA',pricePercent:'0',quantity:1,direction:'buy'},reference())).toThrow(/greater than zero/);
 });
 it('never interprets traditional American odds, unverified sources or stale fee references as percentage prices',()=>{
  expect(()=>draftKingsStandardFill({venue:'CME',pricePercent:'-110',quantity:1,direction:'buy'},reference())).toThrow(/percentage price/);
  expect(()=>draftKingsStandardFill({venue:'CME',pricePercent:'40',quantity:1,direction:'buy'},{...reference(),url:'https://unverified.example.test'})).toThrow(/verified official/);
  vi.useFakeTimers();const ref=reference();vi.setSystemTime(Date.now()+3600001);expect(()=>draftKingsStandardFill({venue:'CME',pricePercent:'40',quantity:1,direction:'buy'},ref)).toThrow(/Freshly verified/);
 });
 it('uses exact decimal arithmetic for large whole-contract quantities and labels the source as a fee reference',()=>{
  const result=draftKingsStandardFill({venue:'CME',pricePercent:'99',quantity:1000000,direction:'buy'},reference());expect(result.cashAmountCents).toBe('100000000');expect(result.source.url).toBe(DRAFTKINGS_FEE_URL);expect(result.kind).toBe('standard_schedule_estimate');
  expect(()=>draftKingsStandardFill({venue:'CME',pricePercent:'40',quantity:1.5,direction:'buy'},reference())).toThrow(/whole contract/);
 });
});
