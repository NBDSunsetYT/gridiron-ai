import {beforeAll,describe,expect,it} from 'vitest';
import {randomUUID} from 'node:crypto';
import {copyFileSync,mkdtempSync,readdirSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {wagerMetadata} from '../lib/wager-record';
import {initializeDatabase} from '../lib/db';
import {filterRecordedWagers,recordedWagerPerformance,recordedWagerSport} from '../lib/wager-performance';

process.env.DATA_DIR=mkdtempSync(join(tmpdir(),'gridiron-contract-ledger-'));
let ledger:typeof import('../lib/ledger'),getDb:typeof import('../lib/db')['getDb'];
beforeAll(async()=>{({getDb}=await import('../lib/db'));ledger=await import('../lib/ledger');});
const contract={sportsbook:'DraftKings',event:'SYNTHETIC recorded event',player:'SYNTHETIC Player',market:'Receiving yards event contract',selection:'YES over40.5',marketInstrument:'event_contract',contractPriceCents:'62.5',contractQuantity:20,entryFeeCents:'25',stake:'12.75'};
function user(){const id=randomUUID();getDb().prepare('INSERT INTO users(id,email,password_hash,created_at)VALUES(?,?,?,?)').run(id,id+'@example.test','SYNTHETIC-HASH',new Date().toISOString());ledger.postTransaction(id,{type:'starting_balance',sportsbook:'DraftKings',amount:'500.00'});return id;}

describe('Actual event-contract financial records',()=>{
 it('validates optional sport metadata without classifying existing wagers or changing predictions',()=>{
  expect(wagerMetadata({...contract,sport:'NFL'},1275).sport).toBe('NFL');
  expect(wagerMetadata({...contract,sport:'CFB'},1275).sport).toBe('CFB');
  for(const sport of ['NFL ', 'nfl','NBA','',null,42,{},['NFL']])expect(()=>wagerMetadata({...contract,sport},1275)).toThrow(/sport/);
  const id=user(),prediction={probability:0.6,modelVersion:'SYNTHETIC-PRESERVED-V1'},bet=ledger.placeBet(id,{...contract,sport:'CFB',prediction});
  ledger.settleBet(id,{id:bet.id,result:'won',payout:'19.80'});
  const read=ledger.getLedger(id).bets.find(row=>row.id===bet.id)!;
  expect(read).toMatchObject({sport:'CFB',prediction,stakeCents:1275,payoutCents:1980});
  expect(getDb().prepare('SELECT sport,prediction FROM bets WHERE id=?').get(bet.id)).toEqual({sport:'CFB',prediction:JSON.stringify(prediction)});
  const legacy=ledger.placeBet(id,{...contract,event:'SYNTHETIC NFL-looking name without recorded sport'});
  expect(recordedWagerSport(ledger.getLedger(id).bets.find(row=>row.id===legacy.id)!)).toBe('Unspecified');
 });
 it('filters actual settled results while leaving capital, transfers and account balances intact',()=>{
  const id=user();ledger.postTransaction(id,{type:'deposit',sportsbook:'DraftKings',amount:'100.00'});ledger.postTransaction(id,{type:'withdrawal',sportsbook:'DraftKings',amount:'150.00'});
  ledger.postTransaction(id,{type:'transfer',sportsbook:'DraftKings',toSportsbook:'Hard Rock',amount:'30.00'});
  const place=(sport:'NFL'|'CFB'|undefined,stake:string,market='Moneyline',sportsbook='DraftKings')=>ledger.placeBet(id,{sportsbook,sport,event:'SYNTHETIC historical event',market,selection:'SYNTHETIC selection',odds:-110,stake,placementTime:'2026-01-01T12:00:00Z'});
  const nfl=place('NFL','42.00');ledger.settleBet(id,{id:nfl.id,result:'won',payout:'100.00',settlementTime:'2026-01-02T12:00:00Z'});
  const cfbVoid=ledger.placeBet(id,{...contract,sport:'CFB',contractPriceCents:'50',contractQuantity:20,entryFeeCents:'0',stake:'10.00',placementTime:'2026-01-01T12:00:00Z'});ledger.settleBet(id,{id:cfbVoid.id,result:'voided',payout:'9.75',settlementTime:'2026-01-03T12:00:00Z'});
  const cfb=place('CFB','20.00','Moneyline','Hard Rock');ledger.settleBet(id,{id:cfb.id,result:'lost',settlementTime:'2026-01-03T12:00:00Z'});
  const unspecified=place(undefined,'5.00');ledger.settleBet(id,{id:unspecified.id,result:'cashed_out',payout:'8.00',settlementTime:'2026-01-04T12:00:00Z'});
  place('NFL','7.00');
  const before=ledger.getLedger(id),nflFiltered=filterRecordedWagers(before.bets,{sport:'NFL'}),cfbFiltered=filterRecordedWagers(before.bets,{sport:'CFB'});
  expect(recordedWagerPerformance(nflFiltered)).toMatchObject({realizedPlCents:'5800',settledStakeCents:'4200',pendingExposureCents:'700'});
  expect(recordedWagerPerformance(cfbFiltered)).toMatchObject({realizedPlCents:'-2025',settledStakeCents:'2000',roi:'-1.0125',voidedBets:1});
  expect(recordedWagerPerformance(filterRecordedWagers(before.bets,{sport:'Unspecified'}))).toMatchObject({realizedPlCents:'300',settledStakeCents:'500'});
  expect(filterRecordedWagers(before.bets,{sport:'CFB',sportsbook:'Hard Rock',market:'Moneyline'}).map(row=>row.id)).toEqual([cfb.id]);
  expect(filterRecordedWagers(before.bets,{sport:'NFL',from:'2026-01-02',to:'2026-01-02'}).map(row=>row.id)).toEqual([nfl.id]);
  expect(recordedWagerPerformance(before.bets)).toMatchObject({realizedPlCents:'4075',settledStakeCents:'6700'});
  expect(ledger.getLedger(id).summary).toEqual(before.summary);
  expect(before.summary).toMatchObject({cashBalanceCents:49075,availableBalanceCents:48375,pendingExposureCents:700,totalDepositsCents:10000,totalWithdrawalsCents:15000,netCashContributedCents:45000,realizedPlCents:4075});
 });
 it('withholds incomplete performance and rejects invalid date bounds instead of assuming money or dates',()=>{
  expect(recordedWagerPerformance([{result:'won',stakeCents:100}])).toMatchObject({incompleteRecords:1,realizedPlCents:null,roi:null});
  expect(filterRecordedWagers([{result:'won',settledAt:'2026-02-01T12:00:00Z'}],{from:'2026-02-30'})).toEqual([]);
  expect(filterRecordedWagers([{result:'pending',placedAt:'2026-02-01T12:00:00Z'}],{from:'2026-02-01',to:'2026-02-01'})).toHaveLength(1);
  expect(recordedWagerPerformance([{result:'won',stakeCents:'90071992547409930000',payoutCents:'90071992547409930001'},{result:'won',stakeCents:'90071992547409930000',payoutCents:'90071992547409930001'}])).toMatchObject({realizedPlCents:'2',settledStakeCents:'180143985094819860000'});
 });
 it('exports recorded sport in authenticated CSV and encrypted snapshots with the original prediction unchanged',async()=>{
  const id=user(),prediction={probability:0.63,modelVersion:'SYNTHETIC-CSV-ORIGINAL'},bet=ledger.placeBet(id,{...contract,sport:'CFB',prediction});
  const legacy=ledger.placeBet(id,{...contract,event:'SYNTHETIC NFL-looking legacy name'});
  const {newSession}=await import('../lib/auth'),token=newSession(id),headers={cookie:'gridiron_session='+token};
  const {GET}=await import('../app/api/ledger/export/route'),response=await GET(new Request('http://localhost/api/ledger/export?kind=bets',{headers})),csv=await response.text();
  expect(response.status).toBe(200);expect(csv).toContain('"sport"');expect(csv).toContain('"CFB"');expect(csv).toContain('"62.5"');
  expect(csv.split('\r\n').find(line=>line.startsWith('"'+legacy.id+'"'))).toContain('"DraftKings","","SYNTHETIC NFL-looking legacy name"');
  const {POST}=await import('../app/api/ledger/backup/route'),password='SYNTHETIC-encrypted-backup-password';
  const backup=await POST(new Request('http://localhost/api/ledger/backup',{method:'POST',headers:{...headers,'content-type':'application/json'},body:JSON.stringify({password})}));
  expect(backup.status).toBe(200);const {decryptBackup}=await import('../lib/backups'),payload=await decryptBackup(await backup.json(),password) as any;
  expect(payload.rawLedger.bets.find((row:any)=>row.id===bet.id)).toMatchObject({sport:'CFB',prediction:JSON.stringify(prediction)});
  expect(payload.ledger.bets.find((row:any)=>row.id===bet.id)).toMatchObject({sport:'CFB',prediction});
  expect(payload.rawLedger.bets.find((row:any)=>row.id===legacy.id).sport).toBeNull();
  const {closeDb}=await import('../lib/db');closeDb();
  expect(ledger.getLedger(id).bets.find(row=>row.id===bet.id)).toMatchObject({sport:'CFB',prediction,stakeCents:1275});
 });
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
  expect(after.market_instrument).toBe('sportsbook');expect(after.contract_price_cents).toBeNull();expect(after.sport).toBeNull();expect(db.pragma('foreign_key_check')).toEqual([]);
  expect(readdirSync(join(directory,'backups')).some(name=>name.endsWith('.sqlite'))).toBe(true);db.close();
 });
});
