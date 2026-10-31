import {describe,it,expect} from 'vitest';
import {accountReportIntent,calculateAccountReport} from '../lib/cloud/account-reports';
const now=new Date('2026-12-01T04:59:59Z'); // November30 in America/New_York after the DST transition.
const tx=(type:string,cents:number,date:string,extra={})=>({type,amountCents:cents,date,sportsbook:'DraftKings',...extra});
const bet=(result:string,stake:number,payout:number|null,settledAt:string|null)=>({sportsbook:'DraftKings',market:'SYNTHETIC accounting only',result,stakeCents:stake,payoutCents:payout,placedAt:'2026-11-01T04:30:00Z',settledAt});
const ledger={transactions:[tx('starting_balance',50000,'2026-01-01T00:00:00Z'),tx('deposit',10000,'2026-11-01T05:00:00Z'),tx('withdrawal',10000,'2026-11-01T04:00:00Z'),tx('withdrawal',5000,'2026-11-01T06:30:00Z',{sportsbook:'Hard Rock'}),tx('withdrawal',99999,'2026-11-01T03:59:59Z'),tx('withdrawal',77777,'2026-12-01T05:00:00Z'),tx('withdrawal',33333,'2026-11-01T12:00:00Z',{reversed:true}),tx('reversal',33333,'2026-11-01T12:00:00Z'),tx('transfer',500,'2026-11-02T12:00:00Z')],bets:[bet('won',4200,10000,'2026-11-01T05:30:00Z'),bet('voided',1000,975,'2026-11-02T05:00:00Z'),bet('pending',3000,null,null)],summary:{cashBalanceCents:50800,availableBalanceCents:47800,pendingExposureCents:3000},accounts:[{sportsbook:'DraftKings',cashBalanceCents:50300,availableBalanceCents:47300,pendingExposureCents:3000},{sportsbook:'Hard Rock',cashBalanceCents:500,availableBalanceCents:500,pendingExposureCents:0}]};
describe('Exact, explicit private account reports without language-model guesses',()=>{
 it('recognizes the requested personal report and refuses research, another person, and unsupported timeframes',()=>{
  expect(accountReportIntent('How much have I withdrawn this month?')).toMatchObject({metrics:['withdrawals'],period:'month',sportsbook:'all'});
  expect(accountReportIntent('Show my recorded deposits this year')).toMatchObject({metrics:['deposits'],period:'year'});
  expect(accountReportIntent('What is my realized P/L?')).toMatchObject({metrics:['realized_pl'],period:'all'});
  expect(accountReportIntent('What is my available Hard Rock balance?')).toMatchObject({metrics:['balance'],sportsbook:'Hard Rock'});
  for(const query of ['Why did my player prop lose?','What is the model probability?','Show the other user withdrawals','How much have I withdrawn last month?','Show my withdrawals this quarter','How much did I withdraw in October?','Show my average monthly deposits','What is my balance since 2025?'])expect(accountReportIntent(query)).toBeNull();
 });
 it('uses local account month boundaries across the fall DST transition and excludes reversals',()=>{
  const answer=calculateAccountReport(ledger,{timezone:'America/New_York'},accountReportIntent('How much have I withdrawn this month?')!,now);
  expect(answer.values.totalWithdrawalsCents).toBe(15000);expect(answer.text).toContain('$150.00');expect(answer.period).toEqual({from:'2026-11-01',toExclusive:'2026-12-01'});expect(answer.timezone).toBe('America/New_York');expect(answer.generatedByAI).toBe(false);expect(answer.citations[0].timestamp).toBe(now.toISOString());
 });
 it('excludes capital movements and pending wagers from realized P/L while retaining an actual void fee loss',()=>{
  const answer=calculateAccountReport(ledger,{timezone:'America/New_York'},accountReportIntent('What is my realized P/L this month?')!,now);
  expect(answer.values.realizedPlCents).toBe(5775);expect(answer.text).toContain('$57.75');expect(answer.text).toContain('Deposits, withdrawals and transfers are excluded');
 });
 it('filters actual books and separates current recorded cash, available balance and exposure',()=>{
  const answer=calculateAccountReport(ledger,{timezone:'America/New_York'},accountReportIntent('What is my Hard Rock balance?')!,now);
  expect(answer.values).toEqual({cashBalanceCents:500,availableBalanceCents:500,pendingExposureCents:0});expect(answer.text).toContain('No language-model response was used');
  expect(calculateAccountReport(ledger,{timezone:'America/New_York'},accountReportIntent('Show my DraftKings withdrawals this month')!,now).values.totalWithdrawalsCents).toBe(10000);
 });
 it('withholds malformed money and invalid timezone data instead of returning approximate figures',()=>{
  expect(()=>calculateAccountReport({...ledger,summary:{cashBalanceCents:1.1}},{timezone:'UTC'},accountReportIntent('What is my balance?')!,now)).toThrow(/exact recorded/);
  expect(()=>calculateAccountReport(ledger,{timezone:'not-a-valid-timezone'},accountReportIntent('Show my deposits this month')!,now)).toThrow(/could not be verified/);
 });
});
