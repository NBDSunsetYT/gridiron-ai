import {beforeAll,describe,expect,it} from 'vitest';
import {randomUUID} from 'node:crypto';
import {copyFileSync,mkdtempSync,readdirSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {wagerMetadata} from '../lib/wager-record';
import {initializeDatabase} from '../lib/db';

process.env.DATA_DIR=mkdtempSync(join(tmpdir(),'gridiron-contract-ledger-'));
let ledger:typeof import('../lib/ledger'),getDb:typeof import('../lib/db')['getDb'];
beforeAll(async()=>{({getDb}=await import('../lib/db'));ledger=await import('../lib/ledger');});
const contract={sportsbook:'DraftKings',event:'SYNTHETIC recorded event',player:'SYNTHETIC Player',market:'Receiving yards event contract',selection:'YES over40.5',marketInstrument:'event_contract',contractPriceCents:'62.5',contractQuantity:20,entryFeeCents:'25',stake:'12.75'};
function user(){const id=randomUUID();getDb().prepare('INSERT INTO users(id,email,password_hash,created_at)VALUES(?,?,?,?)').run(id,id+'@example.test','SYNTHETIC-HASH',new Date().toISOString());ledger.postTransaction(id,{type:'starting_balance',sportsbook:'DraftKings',amount:'500.00'});return id;}

describe('Actual event-contract financial records',()=>{
 it('keeps contract prices and fees distinct from American odds using exact Decimal reconciliation',()=>{
  expect(wagerMetadata(contract,1275)).toEqual({marketInstrument:'event_contract',player:'SYNTHETIC Player',odds:null,contractPriceCents:'62.5',contractQuantity:20,entryFeeCents:'25'});
  expect(()=>wagerMetadata({...contract,stake:'12.74'},1274)).toThrow(/exactly|equal/);
  expect(()=>wagerMetadata({...contract,odds:-110},1275)).toThrow(/without American/);
  expect(()=>wagerMetadata({...contract,entryFeeCents:undefined},1275)).toThrow(/actual total entry fee/);
  expect(()=>wagerMetadata({...contract,contractPriceCents:'62.5000001'},1275)).toThrow(/six decimal/);
  expect(wagerMetadata({...contract,contractPriceCents:'0.29',contractQuantity:100,entryFeeCents:'0'},29).odds).toBeNull();
 });
 it('retains exact fractional-cent fee metadata while cash and settlement remain whole cents',()=>{
  const id=user(),bet=ledger.placeBet(id,{...contract,contractPriceCents:'0.1',contractQuantity:1,entryFeeCents:'0.9',stake:'0.01'});
  expect(ledger.getLedger(id).bets[0]).toMatchObject({contractPriceCents:'0.1',entryFeeCents:'0.9',stakeCents:1,odds:null});
  expect(getDb().prepare('SELECT typeof(entry_fee_cents) AS kind FROM bets WHERE id=?').get(bet.id)).toEqual({kind:'text'});
  ledger.settleBet(id,{id:bet.id,result:'won',payout:'1.00'});expect(ledger.getLedger(id).summary.realizedPlCents).toBe(99);
 });
 it('reserves only actual debited stake and uses actual net settlement once',()=>{
  const id=user(),bet=ledger.placeBet(id,contract);
  expect(ledger.getLedger(id).summary).toMatchObject({cashBalanceCents:50000,availableBalanceCents:48725,pendingExposureCents:1275,realizedPlCents:0});
  expect(()=>ledger.settleBet(id,{id:bet.id,result:'won'})).toThrow(/actual contract/);
  ledger.settleBet(id,{id:bet.id,result:'won',payout:'19.80'});
  const result=ledger.getLedger(id);expect(result.summary).toMatchObject({cashBalanceCents:50705,availableBalanceCents:50705,pendingExposureCents:0,realizedPlCents:705});
  expect(result.bets[0]).toMatchObject({marketInstrument:'event_contract',player:contract.player,odds:null,contractPriceCents:'62.5',contractQuantity:20,entryFeeCents:'25',payoutCents:1980});
  expect(()=>ledger.settleBet(id,{id:bet.id,result:'won',payout:'19.80'})).toThrow(/already/);
 });
 it('records a correct winning contract with a net loss when actual costs exceed its payout',()=>{
  const id=user(),bet=ledger.placeBet(id,{...contract,contractPriceCents:'99',contractQuantity:1,entryFeeCents:'5',stake:'1.04'});
  ledger.settleBet(id,{id:bet.id,result:'won',payout:'1.00'});expect(ledger.getLedger(id).summary.realizedPlCents).toBe(-4);
 });
 it('requires the actual void refund and retains nonrefunded fees as P/L',()=>{
  const id=user(),bet=ledger.placeBet(id,contract);
  expect(()=>ledger.settleBet(id,{id:bet.id,result:'voided'})).toThrow(/actual contract refund/);
  ledger.settleBet(id,{id:bet.id,result:'voided',payout:'12.50'});expect(ledger.getLedger(id).summary).toMatchObject({cashBalanceCents:49975,pendingExposureCents:0,realizedPlCents:-25});
 });
 it('keeps ownership and placement/settlement date checks for contract records',()=>{
  const id=user(),other=user(),bet=ledger.placeBet(id,{...contract,placementTime:'2025-01-03T12:00:00Z'});
  expect(()=>ledger.settleBet(other,{id:bet.id,result:'lost'})).toThrow(/not found/);
  expect(()=>ledger.settleBet(id,{id:bet.id,result:'lost',settlementTime:'2025-01-02T12:00:00Z'})).toThrow(/precede/);
  ledger.settleBet(id,{id:bet.id,result:'lost',settlementTime:'2025-01-04T12:00:00Z'});
  expect(ledger.getLedger(id).bets[0].settledAt).toBe('2025-01-04T12:00:00.000Z');
 });
 it('preserves legacy wager columns exactly through the SQLite nullable-odds migration and retains its checkpoint',()=>{
  const directory=mkdtempSync(join(tmpdir(),'gridiron-legacy-preservation-')),migrations=mkdtempSync(join(tmpdir(),'gridiron-first-three-'));
  for(const name of ['001_initial.sql','002_quant.sql','003_simulation_inputs.sql'])copyFileSync(join(process.cwd(),'migrations',name),join(migrations,name));
  let db=initializeDatabase(directory,migrations);const id=randomUUID(),betId=randomUUID(),at='2025-01-01T12:00:00Z';
  db.prepare('INSERT INTO users(id,email,password_hash,created_at)VALUES(?,?,?,?)').run(id,'SYNTHETIC-'+id+'@example.test','SYNTHETIC-HASH',at);
  db.prepare('INSERT INTO bets(id,user_id,sportsbook,event,market,selection,odds,stake_cents,placed_at,notes,prediction,created_at)VALUES(?,?,?,?,?,?,?,?,?,?,?,?)').run(betId,id,'DraftKings','SYNTHETIC legacy event','Moneyline','SYNTHETIC selection',-110,1000,at,'Original note','{"probability":0.5}',at);
  const prior=db.prepare('SELECT * FROM bets').get() as Record<string,unknown>;db.close();db=initializeDatabase(directory);
  const after=db.prepare('SELECT * FROM bets').get() as Record<string,unknown>;
  for(const [key,value] of Object.entries(prior))expect(after[key]).toEqual(value);
  expect(after.market_instrument).toBe('sportsbook');expect(after.contract_price_cents).toBeNull();expect(db.pragma('foreign_key_check')).toEqual([]);
  expect(readdirSync(join(directory,'backups')).some(name=>name.endsWith('.sqlite'))).toBe(true);db.close();
 });
});
