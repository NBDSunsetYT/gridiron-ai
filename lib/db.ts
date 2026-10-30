import Database from 'better-sqlite3';
import { chmodSync, existsSync, mkdirSync, readFileSync, readdirSync, statSync } from 'node:fs';
import { createHash, randomUUID } from 'node:crypto';
import path from 'node:path';
let instance: Database.Database | undefined;
export type MigrationResult = { applied: string[]; backupPath: string | null };
/** Consistent online SQLite snapshot, including committed WAL transactions. Never copy only the .sqlite file while it is live. */
export function backupDatabase(db: Database.Database, directory: string): string {
  mkdirSync(directory, { recursive: true, mode: 0o700 });
  const destination = path.join(directory, `gridiron-${new Date().toISOString().replace(/[:.]/g,'-')}-${randomUUID().slice(0,8)}.sqlite`);
  db.prepare('VACUUM INTO ?').run(destination);
  chmodSync(destination, 0o600);
  return destination;
}
export function runMigrations(db: Database.Database, migrationsDirectory: string, backupDirectory: string, hasExistingData: boolean): MigrationResult {
  const files = readdirSync(migrationsDirectory).filter(file => /^\d{3}_[a-zA-Z0-9_-]+\.sql$/.test(file)).sort();
  if (!files.length) throw new Error('No database migrations found. Include the migrations directory in the deployment.');
  const migrations = files.map(file => { const sql=readFileSync(path.join(migrationsDirectory,file),'utf8');return {file,sql,checksum:createHash('sha256').update(sql).digest('hex')}; });
  const trackingExists = !!db.prepare("SELECT name FROM sqlite_master WHERE type='table' AND name='schema_migrations'").get();
  const applied = trackingExists ? db.prepare('SELECT name,checksum FROM schema_migrations ORDER BY name').all() as {name:string;checksum:string}[] : [];
  for (const prior of applied) {
    const source=migrations.find(m=>m.file===prior.name);
    if (!source || source.checksum!==prior.checksum) throw new Error(`Applied migration ${prior.name} is missing or changed. Restore the immutable migration file before starting.`);
  }
  const pending=migrations.filter(m=>!applied.some(a=>a.name===m.file));
  if (!pending.length) return {applied:[],backupPath:null};
  // Snapshot before creating the migration-tracking table or changing an existing schema.
  const backupPath=hasExistingData ? backupDatabase(db,backupDirectory) : null;
  db.exec('CREATE TABLE IF NOT EXISTS schema_migrations(name TEXT PRIMARY KEY,checksum TEXT NOT NULL,applied_at TEXT NOT NULL)');
  const completed:string[]=[];
  for(const migration of pending){
    const appliedNow=db.transaction(()=>{
      // Another server worker may have completed the same migration while this connection waited.
      const existing=db.prepare('SELECT checksum FROM schema_migrations WHERE name=?').get(migration.file) as {checksum:string}|undefined;
      if(existing){if(existing.checksum!==migration.checksum)throw new Error(`Applied migration ${migration.file} changed while waiting for the database lock.`);return false;}
      db.exec(migration.sql);db.prepare('INSERT INTO schema_migrations(name,checksum,applied_at) VALUES(?,?,?)').run(migration.file,migration.checksum,new Date().toISOString());return true;
    }).immediate();
    if(appliedNow)completed.push(migration.file);
  }
  return {applied:completed,backupPath};
}
/** Exported for maintenance commands and integration tests; the application uses getDb(). */
export function initializeDatabase(directory: string, migrationsDirectory=path.join(process.cwd(),'migrations')): Database.Database {
  mkdirSync(directory, { recursive: true, mode: 0o700 });
  const filename=path.join(directory,'gridiron.sqlite');
  const hasExistingData=existsSync(filename)&&statSync(filename).size>0;
  const db=new Database(filename);
  try {
    chmodSync(filename,0o600);
    db.pragma('journal_mode = WAL');db.pragma('synchronous = FULL');db.pragma('foreign_keys = ON');db.pragma('busy_timeout = 5000');
    runMigrations(db,migrationsDirectory,path.join(directory,'backups'),hasExistingData);
    return db;
  } catch(error) {db.close();throw error;}
}
export function getDb(): Database.Database {
  if(!instance)instance=initializeDatabase(process.env.DATA_DIR||path.join(process.cwd(),'data'));
  return instance;
}
export function closeDb(): void {if(instance){instance.close();instance=undefined;}}
