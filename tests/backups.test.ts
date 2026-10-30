import { describe, expect, it } from 'vitest';
import { decryptBackup, encryptBackup, type EncryptedBackup } from '../lib/backups';

const password = 'research-backup-password-2026';
const payload = {
  format: 'gridiron-backup-v2', exportedAt: '2026-01-01T00:00:00Z',
  ledger: {
    transactions: [{ id: 'user-recorded-deposit', type: 'deposit', amountCents: 10001, amount: '100.01', sportsbook: 'DraftKings', note: 'Exact decimal cash' }],
    bets: [{ id: 'historical-record', stakeCents: 2500, payoutCents: 4773, prediction: { modelVersion: 'user-import-v1', probability: 0.62 } }],
  },
  research: { conversations: [{ title: 'Research history', messages: [{ role: 'user', content: 'Explain this probability.' }] }], records: [{ kind: 'saved-analysis', data: { note: 'User-provided evidence' } }] },
  preferences: { theme: 'dark', favoriteTeams: ['KC', 'BUF'] },
};

describe('Authenticated encrypted backups', () => {
  it('round-trips money, historical predictions, research and preferences without precision loss', async () => {
    const encrypted = await encryptBackup(payload, password);
    expect(encrypted).toMatchObject({ format: 'gridiron-encrypted-backup-v1', cipher: 'aes-256-gcm', kdf: 'scrypt' });
    expect(JSON.stringify(encrypted)).not.toContain('Exact decimal cash');
    expect(JSON.stringify(encrypted)).not.toContain('research-backup-password');
    expect(await decryptBackup(encrypted, password)).toEqual(payload);
  });
  it('generates different salts, IVs and ciphertext for the same input', async () => {
    const one = await encryptBackup(payload, password);
    const two = await encryptBackup(payload, password);
    expect(one.salt).not.toBe(two.salt);
    expect(one.iv).not.toBe(two.iv);
    expect(one.ciphertext).not.toBe(two.ciphertext);
    expect(await decryptBackup(two, password)).toEqual(payload);
  });
  it('rejects the wrong password instead of returning damaged or partial records', async () => {
    const encrypted = await encryptBackup(payload, password);
    await expect(decryptBackup(encrypted, 'different-password-2026')).rejects.toThrow(/authenticat|password|integrity/i);
  });
  it('rejects tampered ciphertext and authentication tags', async () => {
    const encrypted = await encryptBackup(payload, password);
    const bytes = Buffer.from(encrypted.ciphertext, 'base64'); bytes[0] ^= 1;
    await expect(decryptBackup({ ...encrypted, ciphertext: bytes.toString('base64') }, password)).rejects.toThrow(/authenticat|integrity/i);
    const tag = Buffer.from(encrypted.tag, 'base64'); tag[0] ^= 1;
    await expect(decryptBackup({ ...encrypted, tag: tag.toString('base64') }, password)).rejects.toThrow(/authenticat|integrity/i);
  });
  it('rejects unsupported envelopes and invalid cryptographic parameter lengths', async () => {
    const encrypted = await encryptBackup(payload, password);
    await expect(decryptBackup({ ...encrypted, format: 'unknown-format' } as unknown as EncryptedBackup, password)).rejects.toThrow(/format/i);
    await expect(decryptBackup({ ...encrypted, iv: Buffer.from('short').toString('base64') }, password)).rejects.toThrow(/invalid/i);
    await expect(decryptBackup({ ...encrypted, salt: '' }, password)).rejects.toThrow(/invalid/i);
    await expect(decryptBackup({ ...encrypted, tag: '' }, password)).rejects.toThrow(/invalid/i);
  });
  it('requires a valid backup password for both encryption and decryption', async () => {
    await expect(encryptBackup(payload, 'short')).rejects.toThrow(/12|password/i);
    await expect(encryptBackup(payload, 'a'.repeat(129))).rejects.toThrow(/128|password/i);
    const encrypted = await encryptBackup(payload, password);
    await expect(decryptBackup(encrypted, 'short')).rejects.toThrow(/12|password/i);
  });
});
