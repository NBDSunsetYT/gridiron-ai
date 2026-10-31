import {afterEach,beforeEach,describe,it,expect,vi} from 'vitest';
import Decimal from 'decimal.js';
import {buildPropResearch,exactPropDistribution,rankPropResearch,valueProp} from '../lib/player-props/math';
import {playerPropFixture} from './fixtures/player-props';
import type {PublicGameDetail} from '../lib/public-nfl/types';
import type {PropMarketContract} from '../lib/player-props/market-types';

/** Explicit SYNTHETIC statistical/financial mechanics. Actual source verification
 * is recorded separately and never copied into ordinary production seed data. */
const now='2026-10-30T21:21:51.293Z';
function fixture(){
 const{nfl,receiverYes}=playerPropFixture(),contract=structuredClone(receiverYes.contract),detail=nfl.detail as unknown as PublicGameDetail;
 Object.assign(detail.analysis!.result!,{distributionEncoding:'exact_integer_frequency_v1',engineVersion:'pbp-runtime-6.0.0',players:{'SYNTHETIC-PLAYER':{receivingYards:{histogram:[{value:0,count:2000},{value:64,count:3000},{value:65,count:5000}]}}}});
 contract.category='Receiving yards';return{contract,detail,result:detail.analysis!.result!};
}
function fullTerms(contract:PropMarketContract){
 return{...contract,settlement:{...contract.settlement,unconditionalValuationSupported:true,nonParticipationPolicy:'stat_zero' as const},fees:{...contract.fees,calculationStatus:'verified_explicit' as const,entryFeeCents:'0.015',winFeeCents:'1.1',rounding:'none' as const},yesAskCents:'52.3'};
}
beforeEach(()=>{vi.useFakeTimers({toFake:['Date']});vi.setSystemTime(new Date(now));});
afterEach(()=>vi.useRealTimers());

describe('Exact player-prop research and cost-aware valuation',()=>{
 it('uses exact integer outcomes including zero mass for gt/gte and both binary sides',()=>{
  const{contract,detail}=fixture();
  for(const[threshold,operator,expected]of[[64.5,'gt',.5],[64,'gte',.8],[64,'gt',.5],[0,'gte',1],[0,'gt',.8]] as const){
   const rule={...contract,threshold,operator};
   const yes=buildPropResearch(rule,detail,'YES','SYNTH-RUN'),no=buildPropResearch(rule,detail,'NO','SYNTH-RUN');
   expect(yes.probability.raw).toBe(expected);expect(yes.probability.raw!+no.probability.raw!).toBeCloseTo(1,15);
   expect(yes.probability.calibrated).toBeNull();expect(yes.probability.calibrationStatus).toMatch(/insufficient/i);
  }
 });
 it('rejects unreconciled, duplicate, noninteger, malformed and chart-binned evidence',()=>{
  const{result}=fixture();
  for(const histogram of [[{value:0,count:9999}],[{value:0,count:5000},{value:0,count:5000}],[{value:64.5,count:10000}],[null],[{value:0,count:-1},{value:1,count:10001}]]){
   const malformed={...result,players:{'SYNTHETIC-PLAYER':{receivingYards:{histogram}}}};
   expect(()=>exactPropDistribution(malformed,'SYNTHETIC-PLAYER','receivingYards')).not.toThrow();expect(exactPropDistribution(malformed,'SYNTHETIC-PLAYER','receivingYards')).toBeNull();
  }
  expect(exactPropDistribution({...result,distributionEncoding:'chart_bins_v1'},'SYNTHETIC-PLAYER','receivingYards')).toBeNull();
  const legacy:Record<string,any>={...result,engineVersion:'pbp-runtime-4.0.0'};delete legacy.distributionEncoding;
  expect(exactPropDistribution(legacy,'SYNTHETIC-PLAYER','receivingYards')).not.toBeNull();
  expect(exactPropDistribution({...legacy,engineVersion:'UNKNOWN-ENGINE'},'SYNTHETIC-PLAYER','receivingYards')).toBeNull();
 });
 it('does not manufacture zero probabilities for missing or explicitly withheld players',()=>{
  const{contract,detail,result}=fixture();
  expect(buildPropResearch({...contract,playerId:'SYNTH-MISSING'},detail,'YES','SYNTH-RUN')).toMatchObject({status:'withheld',probability:{raw:null}});
  result.publicPlayerForecastsWithheld={'SYNTHETIC-PLAYER':'SYNTHETIC uncertain availability'};
  const row=buildPropResearch(contract,detail,'YES','SYNTH-RUN');expect(row.probability.raw).toBeNull();expect(row.withheldReasons.join(' ')).toMatch(/availability|withheld/i);
 });
 it('independently rejects mismatched game, stale simulation, invalid threshold and unsupported period',()=>{
  const{contract,detail}=fixture();
  expect(buildPropResearch({...contract,gameId:'SYNTH-OTHER-GAME'},detail,'YES','SYNTH-RUN').probability.raw).toBeNull();
  detail.analysis!.stale=true;expect(buildPropResearch(contract,detail,'YES','SYNTH-RUN').probability.raw).toBeNull();detail.analysis!.stale=false;
  expect(buildPropResearch({...contract,threshold:Number.NaN},detail,'YES','SYNTH-RUN').probability.raw).toBeNull();
  expect(buildPropResearch({...contract,settlement:{...contract.settlement,fullGame:false}},detail,'YES','SYNTH-RUN').probability.raw).toBeNull();
  expect(buildPropResearch({...contract,settlement:{...contract.settlement,overtimeIncluded:false}},detail,'YES','SYNTH-RUN').probability.raw).toBeNull();
 });
 it('keeps conditional participation probabilities separate from unconditional market fair value',()=>{
  const{contract,detail}=fixture(),row=buildPropResearch(contract,detail,'YES','SYNTH-RUN');
  expect(row.status).toBe('conditional');expect(row.probability.raw).toBe(.5);expect(row.probability.conditional).toBe(true);
  expect(row.valuation).toMatchObject({breakEven:null,fairCents:null,netValueCents:null,feesVerified:false});expect(row.valuation.reason).toMatch(/participation|exceptional/i);
  const feesUnknown={...fullTerms(contract),fees:contract.fees};expect(valueProp(feesUnknown,'YES',.6)).toMatchObject({fairCents:'60.000000',breakEven:null,netValueCents:null,feesVerified:false});
 });
 it('calculates exact entry costs, success receipts and expected net value after explicit verified fees',()=>{
  const contract=fullTerms(fixture().contract),value=valueProp(contract,'YES',.63);
  expect(value.entryCostCents).toBe('52.315');expect(value.fairCents).toBe('63.000000');expect(value.netValueCents).toBe('9.99200000');
  expect(value.breakEven).toBeCloseTo(new Decimal('52.315').div('98.9').toNumber(),15);expect(value.feesVerified).toBe(true);
  const rounded=valueProp({...contract,fees:{...contract.fees,rounding:'up_to_cent'}},'YES',.63);
  expect(rounded.entryCostCents).toBe('53.3');expect(rounded.netValueCents).toBe('8.44000000');expect(rounded.breakEven).toBeCloseTo(new Decimal('53.3').div(98).toNumber(),15);
 });
 it('withholds unavailable current prices and invalid money rather than emitting NaN or invented zero fees',()=>{
  const contract=fullTerms(fixture().contract);
  expect(valueProp({...contract,yesAskCents:null},'YES',.63).netValueCents).toBeNull();
  for(const money of['NaN','Infinity','NOT-MONEY','-1']){
   expect(()=>valueProp({...contract,yesAskCents:money},'YES',.63)).not.toThrow();expect(valueProp({...contract,yesAskCents:money},'YES',.63).netValueCents).toBeNull();
   expect(()=>valueProp({...contract,fees:{...contract.fees,entryFeeCents:money}},'YES',.63)).not.toThrow();expect(valueProp({...contract,fees:{...contract.fees,entryFeeCents:money}},'YES',.63).netValueCents).toBeNull();
  }
 });
 it('retains nonzero Wilson sampling uncertainty at observed zero or one hit rates',()=>{
  const{contract,detail}=fixture();
  const zero=buildPropResearch({...contract,threshold:1000},detail,'YES','SYNTH-RUN'),one=buildPropResearch({...contract,threshold:-1},detail,'YES','SYNTH-RUN');
  expect(zero.probability.raw).toBe(0);expect(zero.probability.interval95![1]).toBeGreaterThan(0);
  expect(one.probability.raw).toBe(1);expect(one.probability.interval95![0]).toBeLessThan(1);
  expect(zero.probability.calibrated).toBeNull();expect(one.probability.calibrated).toBeNull();
 });
 it('does not rank the highest probability as the highest verified expected value',()=>{
  const{contract,detail}=fixture(),high=buildPropResearch(contract,detail,'YES','SYNTH-RUN'),value=structuredClone(high);
  high.id='SYNTH-HIGH-P';high.probability.raw=.95;high.valuation=valueProp({...fullTerms(contract),yesAskCents:'99',fees:{...fullTerms(contract).fees,entryFeeCents:'0',winFeeCents:'0'}},'YES',.95);
  value.id='SYNTH-VALUE';value.probability.raw=.6;value.valuation=valueProp({...fullTerms(contract),yesAskCents:'40',fees:{...fullTerms(contract).fees,entryFeeCents:'0',winFeeCents:'0'}},'YES',.6);
  expect(rankPropResearch([high,value])[0].id).toBe('SYNTH-VALUE');
 });
 it('expires quote availability without rewriting captured prices or probability snapshots',()=>{
  const{contract,detail}=fixture(),before=structuredClone(contract),row=buildPropResearch(contract,detail,'YES','SYNTH-RUN',new Date(Date.parse(now)+121000));
  expect(row.stale).toBe(true);expect(row.contract.verification.current).toBe(false);expect(row.valuation.netValueCents).toBeNull();expect(contract).toEqual(before);
  const other=buildPropResearch({...contract,yesAskCents:'90'},detail,'YES','SYNTH-NEXT-RUN');expect(other.id).toBe(buildPropResearch(contract,detail,'YES','SYNTH-RUN').id);
 });
});
