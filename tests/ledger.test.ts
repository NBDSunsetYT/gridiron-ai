import { beforeAll, describe, expect, it } from 'vitest';
import { randomUUID } from 'node:crypto';
import { mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

process.env.DATA_DIR = mkdtempSync(join(tmpdir(), 'gridiron-ledger-tests-'));
let ledger: typeof import('../lib/ledger');
let getDb: typeof import('../lib/db')['getDb'];

beforeAll(async () => {
  ({ getDb } = await import('../lib/db'));
  ledger = await import('../lib/ledger');
});

function user() {
  const id = randomUUID();
  getDb().prepare('INSERT INTO users(id,email,password_hash,created_at) VALUES(?,?,?,?)')
    .run(id, `${id}@example.test`, 'test-password-hash', new Date().toISOString());
  return id;
}
function fund(id: string, amount = '500.00', sportsbook = 'DraftKings') {
  return ledger.postTransaction(id, { type: 'starting_balance', amount, sportsbook });
}
function wager(id: string, stake = '100.00', sportsbook = 'DraftKings') {
  return ledger.placeBet(id, { sportsbook, event: 'User-recorded matchup', market: 'Moneyline', selection: 'Home team', odds: -110, stake });
}
function summary(id: string) { return ledger.getLedger(id).summary; }

describe('Decimal money arithmetic', () => {
  it('converts decimal amounts exactly, including amounts that binary floats cannot represent', () => {
    expect(ledger.moneyToCents('0.10')).toBe(10);
    expect(ledger.moneyToCents('0.20')).toBe(20);
    expect(ledger.moneyToCents('0.29')).toBe(29);
    expect(ledger.moneyToCents('1234567.89')).toBe(123456789);
    expect(ledger.centsToMoney(ledger.moneyToCents('0.10') + ledger.moneyToCents('0.20'))).toBe('0.30');
  });
  it('rejects non-monetary, non-finite, over-precision and unsafe values', () => {
    for (const amount of ['NaN', 'Infinity', 'not money', '0.001', '9007199254740999']) {
      expect(() => ledger.moneyToCents(amount), amount).toThrow();
    }
  });
});

describe('Auditable personal ledger', () => {
  it('separates deposits and withdrawals from betting profit', () => {
    const id = user();
    fund(id);
    ledger.postTransaction(id, { type: 'deposit', amount: '100.00', sportsbook: 'DraftKings' });
    ledger.postTransaction(id, { type: 'withdrawal', amount: '150.00', sportsbook: 'DraftKings' });
    expect(summary(id)).toMatchObject({ cashBalanceCents: 45000, availableBalanceCents: 45000, pendingExposureCents: 0, realizedPlCents: 0, totalDepositsCents: 10000, totalWithdrawalsCents: 15000 });
  });
  it('reserves pending stakes and settles a win without counting the stake twice', () => {
    const id = user();
    fund(id);
    const bet = wager(id);
    expect(summary(id)).toMatchObject({ availableBalanceCents: 40000, pendingExposureCents: 10000, realizedPlCents: 0 });
    ledger.settleBet(id, { id: bet.id, result: 'won', payout: '190.91' });
    expect(summary(id)).toMatchObject({ cashBalanceCents: 59091, availableBalanceCents: 59091, pendingExposureCents: 0, realizedPlCents: 9091 });
    expect(() => ledger.settleBet(id, { id: bet.id, result: 'won', payout: '190.91' })).toThrow();
    expect(summary(id).cashBalanceCents).toBe(59091);
  });
  it('recognizes the full lost stake as a loss', () => {
    const id = user(); fund(id);
    const bet = wager(id, '25.00');
    ledger.settleBet(id, { id: bet.id, result: 'lost' });
    expect(summary(id)).toMatchObject({ cashBalanceCents: 47500, availableBalanceCents: 47500, pendingExposureCents: 0, realizedPlCents: -2500 });
  });
  it('refunds a void and records no betting profit', () => {
    const id = user(); fund(id);
    const bet = wager(id, '75.00');
    ledger.settleBet(id, { id: bet.id, result: 'voided' });
    expect(summary(id)).toMatchObject({ cashBalanceCents: 50000, availableBalanceCents: 50000, pendingExposureCents: 0, realizedPlCents: 0 });
  });
  it('treats cash-out payout as total returned cash, not profit', () => {
    const id = user(); fund(id);
    const bet = wager(id);
    ledger.settleBet(id, { id: bet.id, result: 'cashed_out', payout: '65.00' });
    expect(summary(id)).toMatchObject({ cashBalanceCents: 46500, availableBalanceCents: 46500, pendingExposureCents: 0, realizedPlCents: -3500 });
  });
  it('transfers atomically between sportsbooks without changing portfolio profit or contributions', () => {
    const id = user(); fund(id);
    ledger.postTransaction(id, { type: 'transfer', amount: '125.25', sportsbook: 'DraftKings', toSportsbook: 'Hard Rock' });
    const data = ledger.getLedger(id);
    expect(data.summary).toMatchObject({ cashBalanceCents: 50000, realizedPlCents: 0, totalDepositsCents: 0, totalWithdrawalsCents: 0 });
    expect(data.accounts.find(a => a.sportsbook === 'DraftKings')?.availableBalanceCents).toBe(37475);
    expect(data.accounts.find(a => a.sportsbook === 'Hard Rock')?.availableBalanceCents).toBe(12525);
    expect(() => ledger.postTransaction(id, { type: 'transfer', amount: '9999.00', sportsbook: 'DraftKings', toSportsbook: 'Hard Rock' })).toThrow();
    expect(summary(id).cashBalanceCents).toBe(50000);
  });
  it('rejects spending more available cash, including pending exposure', () => {
    const id = user(); fund(id, '50.00'); wager(id, '40.00');
    expect(() => wager(id, '11.00')).toThrow();
    expect(() => ledger.postTransaction(id, { type: 'withdrawal', amount: '11.00', sportsbook: 'DraftKings' })).toThrow();
    expect(summary(id).availableBalanceCents).toBe(1000);
  });
  it('rejects zero and negative deposits and duplicate settlement without mutating balances', () => {
    const id = user(); fund(id);
    for (const amount of ['0', '-1.00']) {
      expect(() => ledger.postTransaction(id, { type: 'deposit', amount, sportsbook: 'DraftKings' })).toThrow();
    }
    expect(summary(id).cashBalanceCents).toBe(50000);
  });
  it('preserves original entries and appends an auditable correction', () => {
    const id = user(); fund(id);
    const transaction = ledger.postTransaction(id, { type: 'deposit', amount: '25.00', sportsbook: 'DraftKings', note: 'Incorrect deposit' });
    const count = ledger.getLedger(id).transactions.length;
    ledger.reverseTransaction(id, transaction.id, 'Duplicate bank statement entry');
    const data = ledger.getLedger(id);
    expect(data.summary.cashBalanceCents).toBe(50000);
    expect(data.transactions.length).toBeGreaterThan(count);
    expect(data.transactions.some(t => t.id === transaction.id)).toBe(true);
    expect(() => ledger.reverseTransaction(id, transaction.id, 'Second reversal')).toThrow();
  });
  it('scopes reads, settlements and reversals to the owning user', () => {
    const owner = user(); const stranger = user(); fund(owner);
    const bet = wager(owner);
    const tx = ledger.postTransaction(owner, { type: 'deposit', amount: '10.00', sportsbook: 'DraftKings' });
    expect(summary(stranger).cashBalanceCents).toBe(0);
    expect(ledger.getLedger(stranger).transactions).toHaveLength(0);
    expect(() => ledger.settleBet(stranger, { id: bet.id, result: 'won', payout: '190.91' })).toThrow();
    expect(() => ledger.reverseTransaction(stranger, tx.id, 'Not my transaction')).toThrow();
    expect(summary(owner).pendingExposureCents).toBe(10000);
  });
  it('rejects duplicate transaction references atomically', () => {
    const id = user(); fund(id);
    ledger.postTransaction(id, { type: 'deposit', amount: '12.34', sportsbook: 'DraftKings', reference: 'bank-ref-001' });
    expect(() => ledger.postTransaction(id, { type: 'deposit', amount: '12.34', sportsbook: 'DraftKings', reference: 'bank-ref-001' })).toThrow();
    expect(summary(id).cashBalanceCents).toBe(51234);
    const unbalanced = getDb().prepare('SELECT journal_id, SUM(amount_cents) AS total FROM postings GROUP BY journal_id HAVING SUM(amount_cents) != 0').all();
    expect(unbalanced).toHaveLength(0);
  });
  it('preserves placement-time odds and prediction when a recorded bet settles', () => {
    const id = user(); fund(id);
    const prediction = { modelVersion: 'test-v1', probability: 0.6, createdAt: '2026-01-01T00:00:00Z' };
    const bet = ledger.placeBet(id, { sportsbook: 'DraftKings', event: 'Historical user entry', market: 'Moneyline', selection: 'Home', odds: 150, stake: '10.00', prediction });
    ledger.settleBet(id, { id: bet.id, result: 'won' });
    const stored = ledger.getLedger(id).bets.find(b => b.id === bet.id);
    expect(stored?.odds).toBe(150);
    expect(stored?.prediction).toEqual(prediction);
    expect(stored?.payoutCents).toBe(2500);
    expect(summary(id).realizedPlCents).toBe(1500);
  });
  it('enforces a monthly stake limit against recorded wagers', () => {
    const id = user(); fund(id);
    ledger.updateSettings(id, { monthlyLimitCents: 5000 });
    wager(id, '35.00');
    expect(() => wager(id, '20.00')).toThrow();
    expect(summary(id).pendingExposureCents).toBe(3500);
  });
});
