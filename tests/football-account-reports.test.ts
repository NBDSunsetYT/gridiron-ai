import {describe,it,expect} from 'vitest';
import {accountReportIntent,calculateAccountReport} from '../lib/cloud/account-reports';
const now=new Date('2026-10-31T12:00:00Z');
const settlement=(sport:string|null,stakeCents:number,payoutCents:number)=>({sport,result:payoutCents?'won':'lost',sportsbook:'DraftKings',market:'SYNTHETIC accounting fixture',stakeCents,payoutCents,placedAt:'2026-10-01T12:00:00Z',settledAt:'2026-10-02T12:00:00Z'});
const ledger={bets:[settlement('NFL',1000,2500),settlement('CFB',2000,0),settlement(null,500,1000)],transactions:[{type:'deposit',amountCents:10000,date:'2026-10-01T10:00:00Z',sportsbook:'DraftKings'},{type:'withdrawal',amountCents:15000,date:'2026-10-01T11:00:00Z',sportsbook:'DraftKings'}],summary:{cashBalanceCents:45000,availableBalanceCents:45000,pendingExposureCents:0},accounts:[]};
describe('Actual sport-scoped financial evidence',()=>{
 it('keeps the existing unfiltered report while recognizing explicit NFL and CFB requests',()=>{
  expect(accountReportIntent('What is my realized P/L?')).not.toHaveProperty('sport');
  expect(accountReportIntent('What is my CFB realized P/L?')).toMatchObject({sport:'CFB',metrics:['realized_pl']});
  expect(accountReportIntent('Show my NFL realized profit')).toMatchObject({sport:'NFL'});
  expect(accountReportIntent('What is the CFB model probability?')).toBeNull();
 });
 it('uses recorded sport metadata and never assigns old unspecified records to NFL or CFB',()=>{
  const result=(sport:string)=>calculateAccountReport(ledger,{timezone:'UTC'},accountReportIntent(`What is my ${sport} realized P/L?`)!,now);
  expect(result('NFL').values.realizedPlCents).toBe(1500);expect(result('CFB').values.realizedPlCents).toBe(-2000);expect(result('Unspecified').values.realizedPlCents).toBe(500);
  expect(result('CFB').citations[0]).toMatchObject({sport:'CFB'});expect(result('CFB').text).toContain('Records without sport metadata remain Unspecified');
 });
 it('does not attribute deposits, withdrawals or whole-account cash to a selected sport',()=>{
  const answer=calculateAccountReport(ledger,{timezone:'UTC'},accountReportIntent('Show my CFB deposits and withdrawals and balance')!,now);
  expect(answer.values).toMatchObject({totalDepositsCents:10000,totalWithdrawalsCents:15000,cashBalanceCents:45000,availableBalanceCents:45000});expect(answer.text).toContain('remain combined across sports');
  expect(calculateAccountReport(ledger,{timezone:'UTC'},accountReportIntent('What is my realized P/L?')!,now).values.realizedPlCents).toBe(0);
 });
});
