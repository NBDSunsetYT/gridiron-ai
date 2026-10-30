import {beforeAll,afterAll,afterEach,describe,it,expect,vi} from 'vitest';
import {mkdtempSync,rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {randomUUID} from 'node:crypto';
const directory=mkdtempSync(join(tmpdir(),'gridiron-contract-tests-'));
process.env.DATA_DIR=directory;
let db:typeof import('../lib/db');let contracts:typeof import('../lib/contracts');let injuries:typeof import('../lib/injuries');
beforeAll(async()=>{db=await import('../lib/db');contracts=await import('../lib/contracts');injuries=await import('../lib/injuries');});
afterEach(()=>vi.useRealTimers());afterAll(()=>{db.closeDb();rmSync(directory,{recursive:true,force:true});});
function user(){const id=randomUUID();db.getDb().prepare('INSERT INTO users(id,email,password_hash,created_at) VALUES(?,?,?,?)').run(id,id+'@example.test','fixture',new Date().toISOString());return id;}
function quote(id:string){return contracts.saveQuote(id,{contractId:randomUUID(),eventId:'fixture-event',event:'TEST FIXTURE matchup',question:'TEST FIXTURE above threshold?',threshold:64.5,operator:'gt',eventStart:new Date(Date.now()+86400000).toISOString(),settlementRule:'Test fixture official result strictly greater than 64.5.',rulesUrl:'https://example.test/rules',yesAskCents:'60',noAskCents:'42',quotedAt:new Date().toISOString(),sourceUrl:'https://example.test/contract',verified:true,entryFeeCents:'1',winFeeCents:'0',feeSource:'TEST FIXTURE fees'});}
function predict(userId:string,q:any,keys:string[]=[]){return contracts.savePrediction(userId,{quoteId:q.id,probability:.7,side:'YES',quantity:2,asOf:new Date().toISOString(),inputsHash:'fixture-hash',injuryEntityKeys:keys,evidence:{source:'TEST FIXTURE comparable records',method:'External fixture estimate for storage testing',sampleSize:40}});}
describe('immutable contract and injury storage',()=>{
  it('isolates ownership and enforces immutable quote/prediction snapshots',()=>{
    const owner=user(),other=user(),q=quote(owner),p=predict(owner,q);
    expect(()=>predict(other,q)).toThrow(/not found/);
    expect(()=>db.getDb().prepare('UPDATE contract_quotes SET data=? WHERE id=?').run('{}',q.id)).toThrow(/immutable/i);
    expect(()=>db.getDb().prepare('UPDATE prediction_snapshots SET data=? WHERE id=?').run('{}',p.id)).toThrow(/immutable/i);
    expect(contracts.contractHistory(other).quotes).toHaveLength(0);
  });
  it('invalidates referenced changed injuries and queues blocked review without altering predictions',()=>{
    vi.useFakeTimers();vi.setSystemTime(new Date('2026-10-01T12:00:00Z'));
    const owner=user();const base={entityKey:'test-player',player:'TEST FIXTURE player',team:'TEST',status:'questionable',publicationAt:'2026-10-01T11:00:00Z',checkedAt:'2026-10-01T12:00:00Z',sourceUrl:'https://www.nfl.com/injuries',sourceName:'TEST FIXTURE official citation',verified:true,note:'Fixture uncertain status'};
    const first=injuries.saveInjury(owner,base);expect(first.record.availability).toBeNull();
    const q=quote(owner),p=predict(owner,q,['test-player']);
    vi.setSystemTime(new Date('2026-10-01T12:00:02Z'));
    const second=injuries.saveInjury(owner,{...base,status:'out',checkedAt:new Date().toISOString(),note:'TEST FIXTURE updated out designation'});
    expect(second.affectedPredictionIds).toEqual([p.id]);
    expect(contracts.contractHistory(owner).predictions[0].stale).toBe(true);
    const job=db.getDb().prepare('SELECT status,kind FROM simulation_jobs WHERE user_id=?').get(owner);expect(job).toMatchObject({status:'blocked',kind:'injury_resimulation'});
    expect(contracts.contractHistory(owner).predictions[0].injuryVersions[0].id).toBe(first.record.id);
  });
  it('settles hypothetical paper P/L without writing real cash movements and preserves historical scoring',()=>{
    vi.useFakeTimers();vi.setSystemTime(new Date('2026-10-01T12:00:00Z'));
    const owner=user(),q=quote(owner),p=predict(owner,q);contracts.savePaperPosition(owner,{predictionId:p.id});
    vi.setSystemTime(new Date('2026-10-03T12:00:00Z'));
    contracts.settleContract(owner,{contractId:q.contractId,quoteId:q.id,predictionId:p.id,outcome:1,settledAt:new Date().toISOString(),sourceUrl:'https://example.test/result',verified:true});
    const history=contracts.contractHistory(owner);expect(history.paperPositions[0].realizedProfitCents).toBe('78');expect(history.performance.n).toBe(1);expect(history.performance.brier).toBeCloseTo(.09);
    expect(db.getDb().prepare('SELECT COUNT(*) AS n FROM journal WHERE user_id=?').get(owner)).toEqual({n:0});
    expect(()=>contracts.settleContract(owner,{contractId:q.contractId,quoteId:q.id,predictionId:p.id,outcome:0,settledAt:new Date().toISOString(),sourceUrl:'https://example.test/result',verified:true})).toThrow(/already/);
  });
});
