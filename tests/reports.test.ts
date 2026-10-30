import {describe,it,expect} from 'vitest';
import {buildFinancialReport,localDateKey,reportBounds} from '../lib/reports';
const bet=(overrides:Record<string,any>={})=>({sportsbook:'DraftKings',placedAt:'2026-03-07T20:00:00Z',settledAt:'2026-03-09T00:30:00Z',result:'won',stakeCents:10000,payoutCents:17500,...overrides});
const tx=(type:string,cents:number,date='2026-03-08T20:00:00Z',overrides:Record<string,any>={})=>({type,amountCents:cents,date,sportsbook:'DraftKings',...overrides});
describe('Timezone-aware exact financial reports',()=>{
 it('attributes P/L to settlement local day across DST and never counts cash contributions as betting returns',()=>{
  const ledger={bets:[bet()],transactions:[tx('starting_balance',50000),tx('deposit',10000),tx('withdrawal',15000),tx('transfer',5000),tx('promotional_credit',2000),tx('adjustment',-1000),tx('refund',500)]};
  const r=buildFinancialReport(ledger,{timezone:'America/New_York',period:'day',anchor:'2026-03-08'});
  expect(r.totals.realizedPlCents).toBe(7500);expect(r.totals.netCashContributedCents).toBe(45000);expect(r.totals.roi).toBe(.75);
  expect(r.totals.promotionalCreditsCents).toBe(2000);expect(r.totals.adjustmentsCents).toBe(-1000);
  const utc=buildFinancialReport(ledger,{timezone:'UTC',period:'day',anchor:'2026-03-08'});expect(utc.totals.realizedPlCents).toBe(0);
 });
 it('uses calendar periods and Monday-start weeks instead of rolling day approximations',()=>{
  expect(reportBounds('week','2026-03-08')).toEqual({from:'2026-03-02',toExclusive:'2026-03-09'});
  expect(reportBounds('month','2024-02-29')).toEqual({from:'2024-02-01',toExclusive:'2024-03-01'});
  expect(reportBounds('year','2026-12-31')).toEqual({from:'2026-01-01',toExclusive:'2027-01-01'});
  expect(localDateKey('2026-03-09T00:30:00Z','America/New_York')).toBe('2026-03-08');
 });
 it('excludes voided stake, counts cash-out net return once and respects sportsbook filters',()=>{
  const r=buildFinancialReport({bets:[bet({result:'voided',payoutCents:10000}),bet({result:'cashed_out',payoutCents:6000}),bet({sportsbook:'Hard Rock',payoutCents:30000})],transactions:[]},{period:'all',sportsbook:'DraftKings'});
  expect(r.totals.realizedPlCents).toBe(-4000);expect(r.totals.settledStakeCents).toBe(10000);expect(r.totals.voidedBets).toBe(1);expect(r.totals.settledBets).toBe(1);expect(r.totals.roi).toBe(-.4);
 });
 it('ignores reversed deposits and pending bets when calculating profit',()=>{
  const r=buildFinancialReport({bets:[bet({result:'pending',settledAt:null,payoutCents:null})],transactions:[tx('deposit',10000,undefined,{reversed:true}),tx('reversal',-10000),tx('deposit',20000)]},{period:'all'});
  expect(r.totals.realizedPlCents).toBe(0);expect(r.totals.depositsCents).toBe(20000);expect(r.totals.roi).toBeNull();expect(r.totals.wagerStakePlacedCents).toBe(10000);
 });
 it('returns a complete month grid including genuine zero-settlement days without fabricating records',()=>{
  const r=buildFinancialReport({bets:[],transactions:[]},{period:'month',anchor:'2024-02-15',timezone:'UTC'});expect(r.calendar).toHaveLength(29);expect(r.days).toHaveLength(0);expect(r.totals.realizedPlCents).toBe(0);
 });
 it('withholds malformed or inexact financial inputs',()=>{
  expect(()=>buildFinancialReport({bets:[bet({stakeCents:100.1})],transactions:[]})).toThrow(/integer cents/);
  expect(()=>buildFinancialReport({bets:[],transactions:[]},{anchor:'2026-02-30'})).toThrow();
  expect(()=>buildFinancialReport({bets:[],transactions:[]},{timezone:'Not/A_Zone'})).toThrow();
 });
});
