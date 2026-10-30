import { describe, expect, it } from 'vitest';
import { spawnSync } from 'node:child_process';
import { mkdtempSync, mkdirSync, readFileSync, readdirSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import Database from 'better-sqlite3';
import { backupDatabase, initializeDatabase } from '../lib/db';

const temporaryDirectory = () => mkdtempSync(join(tmpdir(), 'gridiron-persistence-'));
function fixture(action: string, directory: string, state?: unknown) {
  const child = spawnSync(process.execPath, ['--import', 'tsx', 'tests/fixtures/persistence-worker.ts', action, ...(state ? [JSON.stringify(state)] : [])], {
    cwd: process.cwd(), encoding: 'utf8', timeout: 30000, env: { ...process.env, DATA_DIR: directory },
  });
  if (child.status !== 0) throw new Error(`Persistence child exited ${child.status}: ${child.stderr || child.error?.message}`);
  if (!child.stdout.trim()) throw new Error(JSON.stringify({ execPath: process.execPath, argv: process.execArgv, envKeys: Object.keys(process.env).filter(key => /VITEST|NODE_OPTIONS|TSX|NODE_V8/.test(key)), child }, null, 2));
  const lines = child.stdout.trim().split('\n');
  return JSON.parse(lines[lines.length - 1]);
}
function migrationsFixture() {
  const directory = temporaryDirectory(); const migrations = join(directory, 'test-migrations'); mkdirSync(migrations);
  writeFileSync(join(migrations, '001_initial.sql'), 'CREATE TABLE durable_marker(id INTEGER PRIMARY KEY, value TEXT NOT NULL);');
  return { directory, migrations };
}

describe('Persistent records across actual process restarts', () => {
  it('retains authenticated sessions, ledger, conversations, preferences and research with owner isolation', () => {
    const directory = temporaryDirectory();
    const seeded = fixture('seed', directory);
    expect(seeded.sessionDigest).toBe(seeded.expectedDigest);
    expect(seeded.sessionDigest).not.toBe(seeded.token);
    const restored = fixture('read', directory, seeded);
    expect(restored.user).toMatchObject({ id: seeded.userId, email: `${seeded.userId}@example.test` });
    expect(restored.ledger.summary.cashBalanceCents).toBe(54025);
    expect(restored.ledger.summary.totalDepositsCents).toBe(4025);
    expect(restored.ledger.transactions).toHaveLength(2);
    expect(restored.conversations).toHaveLength(1);
    expect(restored.conversation.id).toBe(seeded.conversationId);
    expect(JSON.stringify(restored.conversation)).toContain('Explain my recorded bankroll.');
    expect(JSON.stringify(restored.conversation)).toContain('Your recorded balance is $540.25.');
    expect(JSON.stringify(restored.preferences)).toContain('dark');
    expect(JSON.stringify(restored.preferences)).toContain('KC');
    expect(restored.research).toHaveLength(1);
    expect(JSON.stringify(restored.research)).toContain('User-provided research');
    expect(restored.strangerLedger.summary.cashBalanceCents).toBe(0);
    expect(restored.strangerLedger.transactions).toHaveLength(0);
    expect(restored.strangerConversations).toHaveLength(0);
    expect(restored.strangerResearch).toHaveLength(0);
    expect(JSON.stringify(restored.strangerPreferences)).not.toContain('KC');
    expect(restored.forbiddenStatus).toBe(404);
  }, 60000);
});

describe('Ordered, auditable database migrations', () => {
  it('applies each migration once and preserves existing data', () => {
    const { directory, migrations } = migrationsFixture();
    let db = initializeDatabase(directory, migrations);
    db.prepare('INSERT INTO durable_marker(id,value) VALUES(1,?)').run('preserve me'); db.close();
    writeFileSync(join(migrations, '002_extra.sql'), 'CREATE TABLE upgrade_marker(id INTEGER PRIMARY KEY);');
    db = initializeDatabase(directory, migrations);
    expect(db.prepare('SELECT value FROM durable_marker WHERE id=1').get()).toEqual({ value: 'preserve me' });
    expect(db.prepare('SELECT COUNT(*) AS count FROM schema_migrations').get()).toEqual({ count: 2 }); db.close();
    db = initializeDatabase(directory, migrations);
    expect(db.prepare('SELECT COUNT(*) AS count FROM schema_migrations').get()).toEqual({ count: 2 }); db.close();
    expect(readdirSync(join(directory, 'backups')).some(name => name.endsWith('.sqlite'))).toBe(true);
  });
  it('backs up committed WAL records while the source database remains open', () => {
    const { directory, migrations } = migrationsFixture();
    const db = initializeDatabase(directory, migrations);
    db.pragma('wal_autocheckpoint = 0');
    db.prepare('INSERT INTO durable_marker(id,value) VALUES(1,?)').run('committed in WAL');
    const filename = backupDatabase(db, join(directory, 'online-backups'));
    const snapshot = new Database(filename, { readonly: true });
    expect(snapshot.prepare('SELECT value FROM durable_marker WHERE id=1').get()).toEqual({ value: 'committed in WAL' });
    expect(snapshot.pragma('integrity_check', { simple: true })).toBe('ok');
    snapshot.close(); db.close();
  });
  it('rejects modifications to an already applied migration', () => {
    const { directory, migrations } = migrationsFixture();
    initializeDatabase(directory, migrations).close();
    writeFileSync(join(migrations, '001_initial.sql'), 'CREATE TABLE durable_marker(id INTEGER PRIMARY KEY, value TEXT NOT NULL);\n-- changed history');
    expect(() => initializeDatabase(directory, migrations)).toThrow(/checksum|changed|modified|match/i);
    const raw = new Database(join(directory, 'gridiron.sqlite'));
    expect(raw.prepare('SELECT COUNT(*) AS count FROM schema_migrations').get()).toEqual({ count: 1 }); raw.close();
  });
  it('rejects removal of a previously applied migration', () => {
    const { directory, migrations } = migrationsFixture();
    initializeDatabase(directory, migrations).close();
    const emptyMigrations = join(directory, 'empty-migrations'); mkdirSync(emptyMigrations);
    expect(() => initializeDatabase(directory, emptyMigrations)).toThrow(/missing|removed|migration/i);
  });
  it('rolls back a failing migration and can apply a corrected unapplied migration', () => {
    const { directory, migrations } = migrationsFixture();
    let db = initializeDatabase(directory, migrations);
    db.prepare('INSERT INTO durable_marker(id,value) VALUES(1,?)').run('survives failure'); db.close();
    const second = join(migrations, '002_failing.sql');
    writeFileSync(second, 'CREATE TABLE half_applied(id INTEGER PRIMARY KEY); INSERT INTO table_that_does_not_exist VALUES(1);');
    expect(() => initializeDatabase(directory, migrations)).toThrow();
    const raw = new Database(join(directory, 'gridiron.sqlite'));
    expect(raw.prepare("SELECT name FROM sqlite_master WHERE type='table' AND name='half_applied'").get()).toBeUndefined();
    expect(raw.prepare('SELECT value FROM durable_marker WHERE id=1').get()).toEqual({ value: 'survives failure' });
    expect(raw.prepare('SELECT COUNT(*) AS count FROM schema_migrations').get()).toEqual({ count: 1 }); raw.close();
    writeFileSync(second, 'CREATE TABLE half_applied(id INTEGER PRIMARY KEY);');
    db = initializeDatabase(directory, migrations);
    expect(db.prepare("SELECT name FROM sqlite_master WHERE type='table' AND name='half_applied'").get()).toEqual({ name: 'half_applied' });
    expect(db.prepare('SELECT COUNT(*) AS count FROM schema_migrations').get()).toEqual({ count: 2 }); db.close();
  });
  it('upgrades an existing v1 ledger and creates a readable pre-upgrade backup', () => {
    const directory = temporaryDirectory();
    const raw = new Database(join(directory, 'gridiron.sqlite'));
    raw.exec(readFileSync(join(process.cwd(), 'migrations/001_initial.sql'), 'utf8'));
    raw.prepare('INSERT INTO users(id,email,password_hash,created_at) VALUES(?,?,?,?)').run('legacy-user', 'legacy@example.test', 'unused', '2026-01-01T00:00:00.000Z');
    raw.prepare('INSERT INTO journal(id,user_id,type,sportsbook,amount_cents,date,note,created_at) VALUES(?,?,?,?,?,?,?,?)').run('legacy-deposit', 'legacy-user', 'deposit', 'DraftKings', 12345, '2026-01-01T00:00:00.000Z', 'Legacy capital', '2026-01-01T00:00:00.000Z');
    raw.prepare('INSERT INTO postings(journal_id,account,sportsbook,amount_cents) VALUES(?,?,?,?)').run('legacy-deposit', 'cash', 'DraftKings', 12345);
    raw.prepare('INSERT INTO postings(journal_id,account,sportsbook,amount_cents) VALUES(?,?,?,?)').run('legacy-deposit', 'capital', 'DraftKings', -12345);
    raw.close();
    const upgraded = initializeDatabase(directory);
    expect(upgraded.prepare("SELECT SUM(amount_cents) AS cash FROM postings WHERE account='cash'").get()).toEqual({ cash: 12345 });
    expect(upgraded.prepare('SELECT email FROM users WHERE id=?').get('legacy-user')).toEqual({ email: 'legacy@example.test' });
    expect((upgraded.prepare('SELECT COUNT(*) AS count FROM schema_migrations').get() as { count: number }).count).toBeGreaterThanOrEqual(2);
    upgraded.close();
    const backups = readdirSync(join(directory, 'backups')).filter(name => name.endsWith('.sqlite'));
    expect(backups.length).toBeGreaterThanOrEqual(1);
    const backup = new Database(join(directory, 'backups', backups[0]), { readonly: true });
    expect(backup.prepare('SELECT email FROM users WHERE id=?').get('legacy-user')).toEqual({ email: 'legacy@example.test' });
    expect(backup.pragma('integrity_check', { simple: true })).toBe('ok'); backup.close();
  });
});
