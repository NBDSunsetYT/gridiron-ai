/** SYNTHETIC local PostgreSQL boundaries. Never connects to a hosted database. */
import {PGlite} from '@electric-sql/pglite';
import {readFileSync,readdirSync} from 'node:fs';
import assert from 'node:assert/strict';
const db=new PGlite();
await db.exec(`create role anon;create role authenticated;create role service_role bypassrls;create schema auth;create table auth.users(id uuid primary key,email text);create table auth.sessions(id uuid primary key,user_id uuid references auth.users(id));create function auth.uid() returns uuid language sql stable as $$select (nullif(current_setting('request.jwt.claims',true),'')::jsonb->>'sub')::uuid$$;create function auth.jwt() returns jsonb language sql stable as $$select coalesce(nullif(current_setting('request.jwt.claims',true),'')::jsonb,'{}'::jsonb)$$;grant usage on schema auth to authenticated;grant execute on function auth.uid(),auth.jwt() to authenticated;`);
const files=readdirSync(new URL('../migrations/',import.meta.url)).filter(name=>name.endsWith('.sql')).sort();const nflUpgrade=files.find(name=>name.endsWith('_gridiron_nfl_contract_research.sql'));assert.ok(nflUpgrade);const nflCompatibility=files.find(name=>name.endsWith('_gridiron_snapshot_storage_compatibility.sql'));assert.ok(nflCompatibility);
for(const file of files.filter(name=>name!==nflUpgrade&&name!==nflCompatibility&&!name.endsWith('_shared_research_object_storage.sql')))await db.exec(readFileSync(new URL('../migrations/'+file,import.meta.url),'utf8'));
const capability='SYNTHETIC-PUBLIC-PROP-CAPABILITY-ONLY-2026',owner='10000000-0000-4000-8000-000000000011';
await db.query("insert into gridiron_shared_private.capabilities(name,token_sha256) values('public_nfl_ingestion',encode(sha256(convert_to($1,'UTF8')),'hex'))",[capability]);
await db.query('insert into auth.users(id,email)values($1,$2)',[owner,'SYNTHETIC-props@example.test']);
await db.query("select set_config('request.jwt.claims',$1,false)",[JSON.stringify({sub:owner})]);await db.exec('set role authenticated');
await db.query('select public.gridiron_post_transaction($1::jsonb)',[JSON.stringify({type:'deposit',amount:'500.00',sportsbook:'DraftKings'})]);
await db.exec('reset role');
const future=new Date(Date.now()+3600000).toISOString(),at=new Date().toISOString(),lease='60000000-0000-4000-8000-000000000001',wrongLease='60000000-0000-4000-8000-000000000002',simulation='70000000-0000-4000-8000-000000000001';
await db.query("insert into public.shared_nfl_jobs(id,game_id,input_hash,status,data,result)values($1,'SYNTHETIC-GAME','SYNTHETIC-INPUT','completed',$2::jsonb,$3::jsonb)",[simulation,JSON.stringify({simulations:10000}),JSON.stringify({result:{simulations:10000,modelVersion:'SYNTHETIC-PBP-V6'}})]);
await db.exec('set role anon');
const rpc=async payload=>(await db.query('select public.gridiron_prop_write($1,$2::jsonb) value',[capability,JSON.stringify(payload)])).rows[0].value;
await assert.rejects(db.query('select public.gridiron_prop_write($1,$2::jsonb)',['SYNTHETIC-WRONG','{"action":"run_enqueue"}']),/Server capability required/);
await assert.rejects(db.query("insert into public.shared_prop_runs(input_hash)values('SYNTHETIC-direct')"),/permission denied/);
await assert.rejects(db.query('select * from gridiron_shared_private.capabilities'),/permission denied/);
const tables=['runs','contracts','quotes','snapshots','resolutions','model_artifacts','run_results'];
for(const table of tables){assert.equal((await db.query(`select count(*)::int n from public.shared_prop_${table}`)).rows[0].n,0);await assert.rejects(db.query(`delete from public.shared_prop_${table}`),/permission denied/);}
await db.exec('reset role');assert.equal((await db.query("select count(*)::int n from pg_class c join pg_namespace n on n.oid=c.relnamespace where n.nspname='public' and c.relname like 'shared_prop_%' and c.relkind='r' and c.relrowsecurity")).rows[0].n,7);await db.exec('set role anon');
console.log('PROPS SHARED RLS/PUBLIC READ/NO DIRECT WRITE/SCOPED CAPABILITY PASSED');

const run=await rpc({action:'run_enqueue',inputHash:'SYNTHETIC-RUN-HASH',data:{label:'SYNTHETIC isolated local research'}});
assert.equal((await rpc({action:'run_enqueue',inputHash:'SYNTHETIC-RUN-HASH',data:{}})).id,run.id);
assert.equal((await rpc({action:'run_claim',id:run.id,lease})).status,'running');assert.equal(await rpc({action:'run_claim',id:run.id,lease:wrongLease}),null);
await assert.rejects(rpc({action:'run_checkpoint',id:run.id,lease:wrongLease,status:'completed',result:{}}),/Stale research worker lease/);
assert.equal((await rpc({action:'run_checkpoint',id:run.id,lease,status:'queued',data:{cursor:1}})).status,'queued');assert.equal((await rpc({action:'run_claim',id:run.id,lease:wrongLease})).status,'running');
assert.equal((await rpc({action:'run_checkpoint',id:run.id,lease:wrongLease,status:'completed',result:{label:'SYNTHETIC completed'}})).status,'completed');
console.log('PROPS RUN IDEMPOTENCY/LEASE FENCING/BOUNDED CHECKPOINT RESUME PASSED');

const contract={id:'Kalshi:SYNTHETIC-CONTRACT',contractId:'SYNTHETIC-CONTRACT',provider:'Kalshi',eventId:'SYNTHETIC-EVENT',gameId:'SYNTHETIC-GAME',eventStart:future,playerId:'00-0000001',playerName:'SYNTHETIC Player',stat:'receivingYards',threshold:64.5,operator:'gt',sourceKind:'public_exchange',sourceUrl:'https://example.invalid/SYNTHETIC-contract',rulesHash:'SYNTHETIC-VERIFIED-RULE',rules:'SYNTHETIC exact full-game threshold rule',observedAt:at,quotedAt:null,yesAskCents:'52',fees:{calculationStatus:'unverified'}};
const put=(value=contract,hash='SYNTHETIC-QUOTE-A',id='SYNTHETIC-QUOTE-A')=>({action:'contract_put',contract:value,definitionHash:'SYNTHETIC-DEFINITION',quoteHash:hash,quoteId:id});
assert.equal((await rpc(put())).quoteId,'SYNTHETIC-QUOTE-A');assert.equal((await rpc(put({...contract,observedAt:new Date().toISOString()}))).quoteId,'SYNTHETIC-QUOTE-A');
await rpc(put({...contract,yesAskCents:'54'},'SYNTHETIC-QUOTE-B','SYNTHETIC-QUOTE-B'));
assert.equal((await db.query('select count(*)::int n from public.shared_prop_quotes')).rows[0].n,2);assert.equal((await db.query('select data from public.shared_prop_quotes where id=$1',['SYNTHETIC-QUOTE-A'])).rows[0].data.yesAskCents,'52');
await assert.rejects(rpc(put({...contract,threshold:65.5})),/definition cannot change/);await assert.rejects(rpc(put({...contract,playerId:'00-0000002'})),/definition cannot change/);await assert.rejects(rpc(put({...contract,rulesHash:'SYNTHETIC-CHANGED-RULES'})),/definition cannot change/);
await assert.rejects(rpc(put({...contract,id:'SYNTHETIC-PRIVATE',contractId:'SYNTHETIC-PRIVATE',sourceKind:'manual_verified'})),/manual records remain private/);
console.log('PROPS EXACT PLAYER/THRESHOLD/RULE IDENTITY/IMMUTABLE QUOTE HISTORY/PRIVATE MANUAL BOUNDARY PASSED');

const snapshot={id:'SYNTHETIC-SNAPSHOT',runId:run.id,contract,game:{id:'SYNTHETIC-GAME',startTime:future},player:{id:contract.playerId,name:contract.playerName},side:'YES',modelVersion:'SYNTHETIC-PBP-V6',inputVersion:'SYNTHETIC-INPUT',simulationId:simulation,simulations:10000,probability:{raw:.63,calibrated:null,interval95:[.62,.64]},dataQuality:{score:75},valuation:{netValueCents:null},capturedAt:new Date().toISOString()};
const saved=await rpc({action:'snapshot_put',snapshot,quoteId:'SYNTHETIC-QUOTE-A',rank:1100000000});assert.equal(Number(saved.raw_probability),.63);assert.equal(saved.data_quality_score,75);assert.equal(Number(saved.mc_width),.02);
const secondRun=await rpc({action:'run_enqueue',inputHash:'SYNTHETIC-SECOND-RUN',data:{}});
const repeated=await rpc({action:'snapshot_put',snapshot:{...snapshot,runId:secondRun.id,contract:{...contract,yesAskCents:'54'},capturedAt:new Date().toISOString()},quoteId:'SYNTHETIC-QUOTE-B',runId:secondRun.id,rank:3});
assert.equal(repeated.data.runId,run.id);assert.equal(repeated.data.contract.yesAskCents,'52');assert.equal((await db.query('select count(*)::int n from public.shared_prop_run_results')).rows[0].n,2);
await assert.rejects(rpc({action:'snapshot_put',snapshot:{...snapshot,probability:{raw:.9,calibrated:null}},quoteId:'SYNTHETIC-QUOTE-A'}),/Historical prediction identity/);
await assert.rejects(rpc({action:'snapshot_put',snapshot:{...snapshot,id:'SYNTHETIC-UNCALIBRATED',probability:{raw:.63,calibrated:.8}},quoteId:'SYNTHETIC-QUOTE-A'}),/approved matching prop artifact/);
await assert.rejects(rpc({action:'snapshot_put',snapshot:{...snapshot,id:'SYNTHETIC-NO-SIM',simulationId:null},quoteId:'SYNTHETIC-QUOTE-A'}),/matching completed full-game simulation/);
await assert.rejects(rpc({action:'snapshot_put',snapshot:{...snapshot,id:'SYNTHETIC-LATE',capturedAt:future},quoteId:'SYNTHETIC-QUOTE-A'}),/before kickoff/);
const withheld=await rpc({action:'snapshot_put',snapshot:{...snapshot,id:'SYNTHETIC-WITHHELD',simulationId:null,modelVersion:null,inputVersion:null,probability:{raw:null,calibrated:null}},quoteId:'SYNTHETIC-QUOTE-A'});assert.equal(withheld.raw_probability,null);
console.log('PROPS PRE-KICKOFF IMMUTABLE PREDICTIONS/MATCHED FULL-GAME EVIDENCE/NO FAKE CALIBRATION/CROSS-RUN REUSE PASSED');

const batch=await rpc({action:'batch',operations:[put({...contract,yesAskCents:'55'},'SYNTHETIC-QUOTE-C','SYNTHETIC-QUOTE-C'),{action:'run_link',runId:secondRun.id,snapshotIds:[withheld.id],rankOffset:4}]});assert.equal(batch.length,2);
await assert.rejects(rpc({action:'batch',operations:[put({...contract,yesAskCents:'56'},'SYNTHETIC-ROLLBACK','SYNTHETIC-ROLLBACK'),{action:'not_supported'}]}),/Unsupported/);
assert.equal((await db.query("select count(*)::int n from public.shared_prop_quotes where id='SYNTHETIC-ROLLBACK'")).rows[0].n,0);
await assert.rejects(rpc({action:'batch',operations:[{action:'batch',operations:[put()]}]}),/Nested research batches/);
await assert.rejects(rpc({action:'batch',operations:Array.from({length:101},()=>put())}),/1–100/);
console.log('PROPS BATCH ATOMICITY/RETRY/NO NESTED OR UNBOUNDED OPERATIONS PASSED');

// Provider voids can be known before kickoff. Binary statistical outcomes need
// the event to have occurred; personal financial settlements are never written.
const firstResolution={id:'SYNTHETIC-VOID',predictionId:snapshot.id,status:'void',observedValue:null,resolvedAt:new Date().toISOString(),sourceUrl:'https://example.invalid/SYNTHETIC-final-provider',sourceVersion:'SYNTHETIC-FINAL-V1',verifiedFinal:true,rulesHash:contract.rulesHash};
assert.equal((await rpc({action:'resolutions_put',resolutions:[firstResolution]}))[0].status,'void');
assert.equal((await rpc({action:'resolutions_put',resolutions:[{...firstResolution,resolvedAt:new Date().toISOString()}]}))[0].id,firstResolution.id);
await assert.rejects(rpc({action:'resolutions_put',resolutions:[{...firstResolution,id:'SYNTHETIC-BINARY',status:'yes'}]}),/valid final research-resolution time/);
await assert.rejects(rpc({action:'resolutions_put',resolutions:[{...firstResolution,id:'SYNTHETIC-BRANCH',sourceVersion:'SYNTHETIC-FINAL-V2'}]}),/append to the latest resolution/);
await new Promise(resolve=>setTimeout(resolve,15));
const correction={...firstResolution,id:'SYNTHETIC-CORRECTION',previousResolutionId:firstResolution.id,sourceVersion:'SYNTHETIC-FINAL-V2',resolvedAt:new Date().toISOString()};
assert.equal((await rpc({action:'resolutions_put',resolutions:[correction]}))[0].previous_resolution_id,firstResolution.id);
console.log('PROPS FINAL-SOURCE PROVENANCE/IDEMPOTENT APPEND-ONLY CORRECTIONS/NO PRE-GAME BINARY RESULTS PASSED');

const model={id:'SYNTHETIC-CALIBRATOR',protocol:'prop-prospective-game-block-6.0.0',status:'candidate',category:'receivingYards',modelVersion:'SYNTHETIC-PBP-V6',method:'isotonic',createdAt:new Date().toISOString(),dataCutoff:new Date(Date.now()-1000).toISOString(),trainingSampleSize:200,trainingGames:40,blocks:[{upper:.8,n:200,successes:100,probability:.5}]};
assert.equal((await rpc({action:'model_artifact_put',artifact:model})).status,'candidate');
await assert.rejects(rpc({action:'model_artifact_put',artifact:{...model,id:'SYNTHETIC-NO-TRAIN',trainingSampleSize:undefined}}),/sufficient strictly prior/);
await assert.rejects(rpc({action:'model_artifact_put',artifact:{...model,status:'approved',validation:{id:'SYNTHETIC-INVALID'}}}),/subsequent prospective validation/);
await new Promise(resolve=>setTimeout(resolve,15));const firstPredictionAt=new Date().toISOString();await new Promise(resolve=>setTimeout(resolve,15));const lastEventAt=new Date().toISOString();await new Promise(resolve=>setTimeout(resolve,15));
const approved={...model,status:'approved',validation:{id:'SYNTHETIC-VALIDATION',sampleSize:100,games:20,firstPredictionAt,lastEventAt,validatedAt:new Date().toISOString(),brierDifferenceInterval95:[-.05,-.01],logLossDifferenceInterval95:[-.08,-.01]}};
assert.equal((await rpc({action:'model_artifact_put',artifact:approved})).status,'approved');assert.equal((await db.query('select count(*)::int n from public.shared_prop_model_artifacts where id=$1',[model.id])).rows[0].n,2);
await assert.rejects(rpc({action:'model_artifact_put',artifact:{...model,blocks:[]}}),/immutable/);
console.log('PROPS ARCHIVED CANDIDATE/SEPARATE APPROVAL/MINIMUM SAMPLE/PROSPECTIVE CHRONOLOGY PASSED');

await db.exec('reset role');
for(const [table,id]of [['quotes','SYNTHETIC-QUOTE-A'],['snapshots','SYNTHETIC-SNAPSHOT'],['resolutions','SYNTHETIC-VOID'],['model_artifacts','SYNTHETIC-CALIBRATOR']]){
 await assert.rejects(db.query(`update public.shared_prop_${table} set data='{}'::jsonb where id=$1`,[id]),/immutable/);await assert.rejects(db.query(`delete from public.shared_prop_${table} where id=$1`,[id]),/immutable/);
}
assert.equal((await db.query("select p.prosecdef from pg_proc p join pg_namespace n on n.oid=p.pronamespace where n.nspname='public' and p.proname='gridiron_prop_write'")).rows[0].prosecdef,false);
await db.query("select set_config('request.jwt.claims',$1,false)",[JSON.stringify({sub:owner})]);await db.exec('set role authenticated');
const ledger=(await db.query('select public.gridiron_ledger() value')).rows[0].value;assert.equal(ledger.summary.cashBalanceCents,50000);assert.equal(ledger.summary.realizedPlCents,0);
await assert.rejects(rpc({action:'post_transaction',type:'deposit',amount:'1000'}),/Unsupported/);
console.log('PROPS IMMUTABLE HISTORY/INVOKER WRAPPER/PRIVATE LEDGER PRESERVATION PASSED');

// V7 upgrades genuine existing local v6 records rather than resetting fixtures.
await db.exec('reset role');
const beforeUpgrade=(await db.query('select data from public.shared_prop_snapshots where id=$1',[snapshot.id])).rows[0].data;
await db.exec(readFileSync(new URL('../migrations/'+nflUpgrade,import.meta.url),'utf8'));await db.exec(readFileSync(new URL('../migrations/'+nflCompatibility,import.meta.url),'utf8'));
assert.deepEqual((await db.query('select data from public.shared_prop_snapshots where id=$1',[snapshot.id])).rows[0].data,beforeUpgrade,'The v7 migration must never rewrite an existing v6 snapshot.');
await db.query("insert into public.shared_nfl_cache(kind,key,input_hash,data)values('detail','SYNTHETIC-GAME','SYNTHETIC-INPUT',$1::jsonb)",[JSON.stringify({pipelineVersion:'public-nfl-7.0.0',inputVerified:true})]);
await db.exec('set role anon');
const page=async filter=>(await db.query('select public.gridiron_nfl_research_page($1,$2::jsonb) value',[run.id,JSON.stringify(filter)])).rows[0].value;
for(const bad of [{scope:'private'},{ranking:'profit-guaranteed'},{provider:'DraftKings Sportsbook'},{category:'unsupported'},{side:null},{search:{}},{limit:81},{cursor:'-1'},{minQuality:101},{injection:'x'}])await assert.rejects(page(bad),/Unsupported|Invalid|bounded|strings/);
await assert.rejects(db.query('select * from gridiron_shared_private.recovery_checkpoints'),/permission denied/);
const gameContract={...contract,id:'Kalshi:SYNTHETIC-GAME-WINNER',contractId:'SYNTHETIC-GAME-WINNER',playerId:null,playerName:'SYNTHETIC Home',stat:'gameWinner',threshold:0,operator:'gt',subject:{kind:'team',teamId:'HOME'},yesAskCents:'60',noAskCents:'40',verification:{current:true,quoteVerified:true}};
const gamePut=(value,quote='SYNTHETIC-GAME-QUOTE')=>({action:'contract_put',contract:value,definitionHash:'SYNTHETIC-GAME-DEF-'+value.contractId,quoteHash:quote,quoteId:quote});
await rpc(gamePut(gameContract));
await assert.rejects(rpc(gamePut({...gameContract,id:'Kalshi:SYNTHETIC-FAKE-GSIS',contractId:'SYNTHETIC-FAKE-GSIS',playerId:'00-0000001'},'SYNTHETIC-FAKE-QUOTE')),/game_subject_check/);
await assert.rejects(rpc(gamePut({...gameContract,id:'Kalshi:SYNTHETIC-UNSUPPORTED-STAT',contractId:'SYNTHETIC-UNSUPPORTED-STAT',stat:'unsupported'},'SYNTHETIC-UNKNOWN-QUOTE')),/stat_check/);
const legacyAfterUpgrade=await rpc({action:'snapshot_put',snapshot:{...snapshot,id:'SYNTHETIC-V6-AFTER-V7'},quoteId:'SYNTHETIC-QUOTE-A'});assert.equal(legacyAfterUpgrade.data.contract.yesAskCents,'52','Legacy v6 writers must keep full contracts during a rolling upgrade.');assert.equal(legacyAfterUpgrade.data.storageEncoding,undefined);
const gameSnapshot={...snapshot,storageRequest:'nfl_market_snapshot_v7',id:'SYNTHETIC-GAME-SNAPSHOT',contract:gameContract,player:{id:null,name:'SYNTHETIC Home'},probability:{raw:.6,calibrated:null,modelInterval95:[.4,.8],historicalSampleSize:0},sensitivity:{injuryDelta:null}};
const gameSaved=await rpc({action:'snapshot_put',snapshot:gameSnapshot,quoteId:'SYNTHETIC-GAME-QUOTE',rank:2});assert.equal(gameSaved.player_id,null);assert.equal(Number(gameSaved.raw_probability),.6);assert.equal(gameSaved.data.storageEncoding,'nfl_market_snapshot_v7');assert.equal(gameSaved.data.contract,undefined);assert.equal(gameSaved.data.contractRef,'SYNTHETIC-GAME-QUOTE');
const playerWithoutId={...contract,id:'Kalshi:SYNTHETIC-UNMAPPED-PROP',contractId:'SYNTHETIC-UNMAPPED-PROP',playerId:null};
await rpc(gamePut(playerWithoutId,'SYNTHETIC-UNMAPPED-QUOTE'));
await assert.rejects(rpc({action:'snapshot_put',snapshot:{...snapshot,id:'SYNTHETIC-UNMAPPED-RAW',contract:playerWithoutId,player:{id:null,name:playerWithoutId.playerName}},quoteId:'SYNTHETIC-UNMAPPED-QUOTE'}),/model_evidence_check/);
await assert.rejects(rpc({action:'snapshot_put',snapshot:{...gameSnapshot,id:'SYNTHETIC-GAME-NO-SIM',simulationId:null},quoteId:'SYNTHETIC-GAME-QUOTE'}),/matching completed full-game simulation/);
const secondGame={...gameContract,id:'Kalshi:SYNTHETIC-TEAM-TOTAL',contractId:'SYNTHETIC-TEAM-TOTAL',playerName:'SYNTHETIC Team',stat:'teamTotal',threshold:20.5,yesAskCents:'20',noAskCents:'80'};
await rpc(gamePut(secondGame,'SYNTHETIC-TEAM-QUOTE'));
await rpc({action:'snapshot_put',snapshot:{...gameSnapshot,id:'SYNTHETIC-TEAM-SNAPSHOT',contract:secondGame,player:{id:null,name:secondGame.playerName},probability:{raw:.5,calibrated:null,modelInterval95:[.45,.55],historicalSampleSize:0}},quoteId:'SYNTHETIC-TEAM-QUOTE',rank:1});
let games=await page({scope:'game',limit:1});assert.equal(games.total,2);assert.equal(games.rows[0].id,'SYNTHETIC-TEAM-SNAPSHOT');assert.equal(games.nextCursor,'1');assert.equal(games.rows[0].contract.rulesHash,contract.rulesHash);
const next=await page({scope:'game',cursor:games.nextCursor,limit:1});assert.equal(next.rows[0].id,gameSnapshot.id);assert.equal(next.rows[0].contract.yesAskCents,'60');assert.equal(next.nextCursor,null);
assert.equal((await page({scope:'game',provider:'DraftKings Predictions'})).total,0,'An absent primary feed must not silently return alternative quotes.');
assert.equal((await page({scope:'game',category:'gameWinner',side:'YES',search:'Home'})).total,1);
assert.equal((await page({scope:'game',ranking:'calibrated'})).total,0,'No fake calibrated ranking without an approved artifact.');
assert.equal((await page({scope:'game',ranking:'reliability'})).total,0);assert.equal((await page({scope:'game',ranking:'injury'})).total,0);
const narrow=await page({scope:'game',ranking:'uncertainty'});assert.equal(narrow.rows[0].id,'SYNTHETIC-TEAM-SNAPSHOT');assert.equal(Number(narrow.rows[0].rankingMetrics.uncertaintyWidth),.1);
const disagreements=await page({scope:'game',ranking:'disagreement'});assert.equal(disagreements.rows[0].id,'SYNTHETIC-TEAM-SNAPSHOT');assert.equal(Number(disagreements.rows[0].rankingMetrics.modelMarketDifference),.3);
await new Promise(resolve=>setTimeout(resolve,15));await rpc(gamePut({...gameContract,observedAt:new Date().toISOString(),yesAskCents:'65'},'SYNTHETIC-CHANGED-GAME-QUOTE'));
const moved=await page({scope:'game',category:'gameWinner',ranking:'movement'});assert.equal(moved.total,1);assert.equal(Number(moved.rows[0].rankingMetrics.priceChange),5);assert.equal(moved.rows[0].contract.yesAskCents,'60','Current movement must not rewrite original captured price.');
await db.exec('reset role');await db.query("update public.shared_nfl_cache set updated_at=now()-interval '31 minutes' where kind='detail' and key='SYNTHETIC-GAME'");await db.exec('set role anon');assert.equal((await page({scope:'game',ranking:'uncertainty'})).total,0,'Stale model inputs cannot rank as current evidence.');assert.equal((await page({scope:'game'})).total,2,'Stale evidence remains preserved and visible as historical research.');
await db.exec('reset role');assert.equal((await db.query("select prosecdef from pg_proc where oid='public.gridiron_nfl_research_page(uuid,jsonb)'::regprocedure")).rows[0].prosecdef,false);await db.exec('set role authenticated');assert.equal((await rpc({action:'run_enqueue',inputHash:'SYNTHETIC-NEW-RUN',data:{}})).status,'queued');
console.log('NFL GAME/PLAYER IDENTITY/GLOBAL RANKING/EXACT RULES/COMPACT IMMUTABLE HISTORY/RLS/STALE WITHHOLDING PASSED');

// Force a storage-capacity boundary only inside this disposable local database.
// This exercises failure/restore paths without filling a real database or billing a provider.
await db.exec('reset role');const sizeFunction=(await db.query("select pg_get_functiondef('gridiron_shared_private.has_public_storage_headroom()'::regprocedure) definition")).rows[0].definition;
const capacityJob='70000000-0000-4000-8000-000000000099';await db.query("insert into public.shared_nfl_jobs(id,game_id,input_hash,status,data,lease)values($1,'SYNTHETIC-CAPACITY-GAME','SYNTHETIC-CAPACITY-INPUT','running','{\"simulations\":10000}'::jsonb,$2)",[capacityJob,lease]);
await db.exec('create or replace function gridiron_shared_private.has_public_storage_headroom() returns boolean language sql volatile security invoker set search_path=pg_catalog as $$select false$$');
await db.exec('set role anon');
await assert.rejects(db.query('select gridiron_shared_private.has_public_storage_headroom()'),/permission denied/);
await assert.rejects(rpc(gamePut({...gameContract,id:'Kalshi:SYNTHETIC-CAPACITY-CONTRACT',contractId:'SYNTHETIC-CAPACITY-CONTRACT'},'SYNTHETIC-CAPACITY-QUOTE')),/preserve personal-record storage/);
await assert.rejects(rpc({action:'snapshot_put',snapshot:{...gameSnapshot,id:'SYNTHETIC-CAPACITY-SNAPSHOT'},quoteId:'SYNTHETIC-GAME-QUOTE'}),/preserve personal-record storage/);
const shared=async payload=>(await db.query('select public.gridiron_public_write($1,$2::jsonb) value',[capability,JSON.stringify(payload)])).rows[0].value;
assert.equal((await shared({action:'job_enqueue',gameId:'SYNTHETIC-GAME',inputHash:'SYNTHETIC-INPUT',data:{}})).id,simulation,'Cached jobs remain reusable at capacity.');
await assert.rejects(shared({action:'job_enqueue',gameId:'SYNTHETIC-NO-CAPACITY',inputHash:'SYNTHETIC-NEW-CAPACITY-INPUT',data:{simulations:10000}}),/preserve personal-record storage/);
await assert.rejects(shared({action:'job_complete',id:capacityJob,lease,result:{simulations:10000}}),/preserve personal-record storage/);
assert.equal((await shared({action:'job_fail',id:capacityJob,lease,error:'SYNTHETIC capacity pause'})).status,'failed','Fenced failure checkpoints must remain writable.');
await db.exec('reset role');await db.query("select set_config('request.jwt.claims',$1,false)",[JSON.stringify({sub:owner})]);await db.exec('set role authenticated');
await db.query('select public.gridiron_post_transaction($1::jsonb)',[JSON.stringify({type:'deposit',amount:'0.01',sportsbook:'DraftKings'})]);await db.query('select public.gridiron_post_transaction($1::jsonb)',[JSON.stringify({type:'withdrawal',amount:'0.01',sportsbook:'DraftKings'})]);assert.equal((await db.query('select public.gridiron_ledger() value')).rows[0].value.summary.cashBalanceCents,50000);assert.equal((await db.query('select public.gridiron_ledger() value')).rows[0].value.summary.realizedPlCents,0,'Storage admission must not block personal financial records or count cash movements as profit.');
await db.exec('reset role');await db.exec(sizeFunction);
console.log('PUBLIC STORAGE CAPACITY/EXISTING CACHED JOBS/FENCED FAILURE/PRIVATE FINANCIAL HEADROOM PASSED');


await db.close();
