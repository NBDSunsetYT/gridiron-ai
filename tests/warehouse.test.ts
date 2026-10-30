import {afterAll,beforeAll,describe,expect,it} from 'vitest';
import {mkdtempSync,rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {randomUUID} from 'node:crypto';
import {easternKickoff,normalizeSchedules,parseWarehouseCSV,warehouseId} from '../lib/warehouse';
const header='game_id,season,gameday,gametime,home_team,away_team,home_score,away_score,home_qb_id,home_qb_name,away_qb_id,away_qb_name\n';
const raw=header+'SYNTHETIC-1,2023,2023-11-30,20:15,AAA,BBB,28,21,QB-A,Synthetic QB A,QB-B,Synthetic QB B\nSYNTHETIC-2,2023,2023-12-01,,AAA,BBB,21,14,,,,\n';
describe('Historical warehouse provenance and identity',()=>{
 it('uses documented Eastern timezone with DST instead of guessing UTC/noon',()=>{expect(easternKickoff('2023-11-30','20:15')).toBe('2023-12-01T01:15:00.000Z');expect(easternKickoff('2023-09-10','20:15')).toBe('2023-09-11T00:15:00.000Z');expect(easternKickoff('2023-09-10','')).toBeNull();expect(easternKickoff('2023-03-12','02:30')).toBeNull();});
 it('excludes unknown kickoff and preserves unknown publication time as null',()=>{const r=normalizeSchedules(raw,{seasonFrom:2023,seasonTo:2023,collectedAt:'2026-10-30T12:00:00Z'});expect(r.receipt.games).toBe(1);expect(r.receipt.skipped.missingKickoff).toBe(1);expect(r.rows.every(x=>x.availableAt===null&&Boolean(x.version)&&Boolean(x.source)&&Boolean(x.collectedAt)&&Boolean(x.eventAt))).toBe(true);expect(r.rows.find(x=>x.kind==='games')?.data.homeScore).toBe(28);});
 it('does not create scores or usage from missing observations',()=>{const r=normalizeSchedules(header+'SYNTHETIC,2023,2023-12-01,13:00,AAA,BBB,,,,,,\n',{seasonFrom:2023,seasonTo:2023});expect(r.rows.find(x=>x.kind==='games')?.data.status).toBe('scheduled');expect(r.rows.find(x=>x.kind==='games')?.data.homeScore).toBeNull();expect(r.rows.some(x=>x.kind==='player_statistics')).toBe(false);});
 it('parses quoted evidence without executing text and scopes deterministic identities',()=>{expect(parseWarehouseCSV('id,note\na,"Two, fields"\n')[0].note).toBe('Two, fields');expect(warehouseId('owner-a','games','game')).not.toBe(warehouseId('owner-b','games','game'));});
});
const directory=mkdtempSync(join(tmpdir(),'gridiron-warehouse-test-'));process.env.DATA_DIR=directory;
let db:typeof import('../lib/db');beforeAll(async()=>{db=await import('../lib/db');});afterAll(()=>{db.closeDb();rmSync(directory,{recursive:true,force:true});});
it('idempotent source retries preserve append-only history and account isolation',async()=>{const {localWarehouseStorage}=await import('../lib/warehouse');const owner=randomUUID(),other=randomUUID(),now=new Date().toISOString();for(const id of [owner,other])db.getDb().prepare('INSERT INTO users(id,email,password_hash,created_at) VALUES(?,?,?,?)').run(id,id+'@example.test','SYNTHETIC',now);const r=normalizeSchedules(raw,{seasonFrom:2023,seasonTo:2023});const store=localWarehouseStorage(owner);expect((await store.commit(r.rows,r.receipt)).duplicate).toBe(false);expect((await store.commit(r.rows,r.receipt)).duplicate).toBe(true);expect(await store.list('games')).toHaveLength(1);expect(await localWarehouseStorage(other).list()).toHaveLength(0);expect(()=>db.getDb().prepare('UPDATE warehouse_records SET source=? WHERE user_id=?').run('tamper',owner)).toThrow();});
