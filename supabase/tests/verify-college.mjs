/** Disposable SYNTHETIC PostgreSQL integration checks. Never connects to a
 * managed project, changes a real budget, or creates production accounts. */
import {PGlite} from '@electric-sql/pglite';
import {readFileSync,readdirSync} from 'node:fs';
import assert from 'node:assert/strict';
const db=new PGlite(),directory=new URL('../migrations/',import.meta.url),checks=[];
const files=readdirSync(directory).filter(name=>name.endsWith('.sql')).sort(),upgrade=files.find(name=>name.endsWith('_gridiron_v8_football.sql'));assert.ok(upgrade,'A versioned football migration is required.');
await db.exec(`create role anon;create role authenticated;create role service_role bypassrls;create schema auth;create table auth.users(id uuid primary key,email text);create table auth.sessions(id uuid primary key,user_id uuid references auth.users(id));create function auth.uid() returns uuid language sql stable as $$select (nullif(current_setting('request.jwt.claims',true),'')::jsonb->>'sub')::uuid$$;create function auth.jwt() returns jsonb language sql stable as $$select coalesce(nullif(current_setting('request.jwt.claims',true),'')::jsonb,'{}'::jsonb)$$;grant usage on schema auth to authenticated;grant execute on function auth.uid(),auth.jwt() to authenticated;`);
for(const file of files.filter(name=>name<upgrade))await db.exec(readFileSync(new URL(file,directory),'utf8'));
const capability='SYNTHETIC-FOOTBALL-CAPABILITY-LOCAL-TEST-ONLY-2026',A='10000000-0000-4000-8000-000000000081',B='10000000-0000-4000-8000-000000000082',at=new Date().toISOString(),future=new Date(Date.now()+86400000).toISOString(),hash='a'.repeat(64),lease='60000000-0000-4000-8000-000000000081',otherLease='60000000-0000-4000-8000-000000000082',thirdLease='60000000-0000-4000-8000-000000000083';
await db.query("insert into gridiron_shared_private.capabilities(name,token_sha256)values('public_nfl_ingestion',encode(sha256(convert_to($1,'UTF8')),'hex'))",[capability]);
for(const id of[A,B])await db.query('insert into auth.users(id,email)values($1,$2)',[id,'SYNTHETIC-'+id+'@example.test']);
// A pre-existing NFL reservation remains in the SAME shared UTC pool after v8.
await db.query("insert into gridiron_shared_private.compute_budget(day,games)values((now() at time zone 'UTC')::date,390000)");
const owner=async id=>{await db.exec('reset role');await db.query("select set_config('request.jwt.claims',$1,false)",[JSON.stringify({sub:id})]);await db.exec('set role authenticated');};
const personal=async(name,payload)=>(await db.query(payload===undefined?`select public.${name}() value`:`select public.${name}($1::jsonb) value`,payload===undefined?[]:[JSON.stringify(payload)])).rows[0].value;
await owner(A);await personal('gridiron_post_transaction',{type:'starting_balance',sportsbook:'DraftKings',amount:'500.00'});const financialBefore=(await personal('gridiron_ledger')).summary;await db.exec('reset role');
await db.exec(readFileSync(new URL(upgrade,directory),'utf8'));for(const file of files.filter(name=>name>upgrade))await db.exec(readFileSync(new URL(file,directory),'utf8'));await db.exec('set role anon');
const rpc=async(payload,token=capability)=>(await db.query('select public.gridiron_football_data_write($1,$2::jsonb) value',[token,JSON.stringify(payload)])).rows[0].value;
async function admin(operation){const role=(await db.query('select current_user role')).rows[0].role;await db.exec('reset role');try{return await operation();}finally{if(['anon','authenticated'].includes(role))await db.exec('set role '+role);}}
const budget=async()=>Number((await admin(()=>db.query("select games from gridiron_shared_private.compute_budget where day=(now() at time zone 'UTC')::date"))).rows[0].games);
const count=async table=>(await db.query(`select count(*)::int n from public.${table}`)).rows[0].n;
async function group(name,run){try{await run();checks.push({name,status:'passed'});console.log('PASS '+name);}catch(error){checks.push({name,status:'failed',message:String(error.message).slice(0,350)});console.error('FAIL '+name+': '+String(error.message).slice(0,350));}}
const shared=['football_data_sources','cfb_conferences','cfb_teams','cfb_players','cfb_games','cfb_plays','cfb_team_statistics','cfb_player_statistics','cfb_injuries','cfb_rankings','cfb_depth_charts','cfb_model_versions','shared_cfb_cache','provider_market_quotes'],privateTables=['cfb_simulation_runs','cfb_prediction_snapshots'];
await group('Additive migration keeps the existing 390k shared reservation and enables RLS on all 16 new tables',async()=>{assert.equal(await budget(),390000);const rows=(await admin(()=>db.query("select c.relname,c.relrowsecurity from pg_class c join pg_namespace n on n.oid=c.relnamespace where n.nspname='public' and c.relname=any($1)",[[...shared,...privateTables]]))).rows;assert.equal(rows.length,16);assert.ok(rows.every(row=>row.relrowsecurity));});
await group('Guests may read shared data but cannot write it, read private history, or inspect capability/budget tables',async()=>{for(const table of shared){assert.equal(await count(table),0);await assert.rejects(db.query(`insert into public.${table} default values`),/permission denied/);await assert.rejects(db.query(`update public.${table} set sport='CFB' where false`),/permission denied/);await assert.rejects(db.query(`delete from public.${table} where false`),/permission denied/);}for(const table of privateTables)await assert.rejects(db.query(`select * from public.${table}`),/permission denied/);for(const table of['capabilities','compute_budget','cfb_compute_reservations'])await assert.rejects(db.query(`select * from gridiron_shared_private.${table}`),/permission denied/);});
await group('The public invoker wrapper requires the real scoped capability before any status or write',async()=>{for(const token of['','SYNTHETIC-WRONG-TOKEN-THAT-IS-LONG-ENOUGH-2026',null])await assert.rejects(rpc({action:'status'},token),/Server capability required/);await assert.rejects(db.query('select gridiron_shared_private.football_data_write_operation($1,$2::jsonb)',['SYNTHETIC-WRONG','{"action":"status"}']),/Server capability required/);assert.equal((await admin(()=>db.query("select p.prosecdef from pg_proc p join pg_namespace n on n.oid=p.pronamespace where n.nspname='public' and p.proname='gridiron_football_data_write'"))).rows[0].prosecdef,false);assert.equal((await rpc({action:'status'})).admissionAvailable,true);});
const source={id:'SYNTHETIC-CFB-SOURCE',sport:'CFB',provider:'ESPN',source_url:'https://example.invalid/SYNTHETIC-cfb-source',collected_at:at,available_at:at,event_time:at,source_version:'SYNTHETIC-V1',reliability:'verified',data:{label:'SYNTHETIC public provenance only'}},nflSource={...source,id:'SYNTHETIC-NFL-SOURCE',sport:'NFL',provider:'BallDontLie'};
const common={sport:'CFB',source_id:source.id,source_version:'SYNTHETIC-V1',collected_at:at,available_at:at,event_time:at,reliability:'verified',data:{label:'SYNTHETIC public college evidence'}};
const entity=(table,row)=>rpc({action:'entity_put',table,row:{...common,...row}});
await group('All college warehouse families accept properly sourced CFB identifiers and preserve cross-sport foreign keys',async()=>{
 assert.equal((await rpc({action:'source_put',row:source})).id,source.id);await rpc({action:'source_put',row:nflSource});
 await entity('cfb_conferences',{id:'cfb:conference:SYNTHETIC',provider_id:'SYNTHETIC',name:'SYNTHETIC conference'});
 for(const id of['home','away'])await entity('cfb_teams',{id:'cfb:team:'+id,provider_id:'SYNTHETIC-'+id,name:'SYNTHETIC '+id,conference_id:'cfb:conference:SYNTHETIC',classification:'fbs'});
 await entity('cfb_players',{id:'cfb:player:one',provider_id:'SYNTHETIC-player',name:'SYNTHETIC player',team_id:'cfb:team:home',position:'WR'});
 await entity('cfb_games',{id:'cfb:game:one',provider_id:'SYNTHETIC-game',season:2026,week:1,home_team_id:'cfb:team:home',away_team_id:'cfb:team:away',kickoff_at:future,kickoff_verified:true,status:'scheduled'});
 await entity('cfb_plays',{id:'cfb:play:one',game_id:'cfb:game:one',source_play_id:'SYNTHETIC-play',offense_team_id:'cfb:team:home',defense_team_id:'cfb:team:away',receiver_id:'cfb:player:one',down:1,distance:10,seconds_remaining:3500});
 await entity('cfb_team_statistics',{id:'cfb:team-stat:one',team_id:'cfb:team:home',game_id:'cfb:game:one',season:2026,metric:'SYNTHETIC-EPA',value:0.1});
 await entity('cfb_player_statistics',{id:'cfb:player-stat:one',player_id:'cfb:player:one',game_id:'cfb:game:one',season:2026,metric:'SYNTHETIC-yards',value:50});
 await entity('cfb_injuries',{id:'cfb:injury:one',player_id:'cfb:player:one',player_name:'SYNTHETIC player',team_id:'cfb:team:home',game_id:'cfb:game:one',status:'questionable',practice_participation:'limited',availability:'uncertain',official_confirmed:false});
 await entity('cfb_rankings',{id:'cfb:ranking:one',team_id:'cfb:team:home',season:2026,week:1,poll:'SYNTHETIC',rank:1});
 await entity('cfb_depth_charts',{id:'cfb:depth:one',team_id:'cfb:team:home',player_id:'cfb:player:one',position:'WR',depth:1});
 for(const approval of['candidate','approved'])await entity('cfb_model_versions',{id:'cfb:model:'+approval,model_version:'SYNTHETIC-CFB-V1',model_kind:'calibration',approval_status:approval});
 await assert.rejects(entity('cfb_teams',{id:'cfb:team:bad-source',provider_id:'SYNTHETIC-bad',name:'SYNTHETIC invalid source',source_id:nflSource.id}),/foreign key/);
 await assert.rejects(entity('cfb_teams',{id:'nfl:team:bad',provider_id:'SYNTHETIC-bad',name:'SYNTHETIC invalid prefix'}),/check constraint/);
 await assert.rejects(entity('cfb_teams',{id:'cfb:team:wrong-sport',provider_id:'SYNTHETIC-bad',name:'SYNTHETIC wrong sport',sport:'NFL'}),/check constraint|CFB/);
 await assert.rejects(rpc({action:'entity_put',table:'ledger_entries',row:{}}),/supported CFB/);
});
const quote={id:'SYNTHETIC-NFL-BDL-QUOTE',sport:'NFL',provider:'BallDontLie',marketFamily:'sportsbook_reference',eventId:'SYNTHETIC-NFL-EVENT',marketId:'SYNTHETIC-YARDS',selection:'SYNTHETIC OVER',line:'50.5',americanOdds:-110,bidCents:null,askCents:null,quotedAt:at,observedAt:at,sourceUrl:'https://example.invalid/SYNTHETIC-quote',data:{label:'SYNTHETIC reference quote'}};
await group('NFL/CFB sportsbook references and percentage event contracts cannot be relabeled across venues or instruments',async()=>{
 await rpc({action:'provider_quote_put',quote});await rpc({action:'provider_quote_put',quote:{...quote,id:'SYNTHETIC-CFB-CFDB',sport:'CFB',provider:'CollegeFootballData'}});
 for(const provider of['DraftKings Predictions','Kalshi'])await rpc({action:'provider_quote_put',quote:{...quote,id:'SYNTHETIC-'+provider,provider,marketFamily:'event_contract',americanOdds:null,bidCents:'49',askCents:'51'}});
 const invalid=[{sport:'CFB'},{marketFamily:'event_contract',americanOdds:null},{provider:'CollegeFootballData'},{provider:'DraftKings Predictions'},{provider:'Kalshi'},{americanOdds:-99},{marketFamily:'event_contract',provider:'DraftKings Predictions',americanOdds:null,askCents:'101'},{quotedAt:new Date(Date.parse(at)+120000).toISOString()},{sourceUrl:'https://example.invalid/feed?api_key=SYNTHETIC'},{sourceUrl:'https://SYNTHETIC@provider.example.invalid/feed'}];
 for(let i=0;i<invalid.length;i++)await assert.rejects(rpc({action:'provider_quote_put',quote:{...quote,...invalid[i],id:'SYNTHETIC-INVALID-QUOTE-'+i}}),/check constraint|secret|source|provider/i);
});
await group('PropLine NFL/CFB quote writes retain immutable sportsbook family and enforce provider identity',async()=>{
 for(const sport of ['NFL','CFB']){const q={...quote,id:'SYNTHETIC-PROPLINE-'+sport,sport,provider:'PropLine'};assert.equal((await rpc({action:'provider_quote_put',quote:q})).provider,'PropLine');await assert.rejects(rpc({action:'provider_quote_put',quote:{...q,americanOdds:100}}),{code:'22023'});}
 await assert.rejects(rpc({action:'provider_quote_put',quote:{...quote,id:'SYNTHETIC-NOT-A-DK-CONTRACT',provider:'PropLine',marketFamily:'event_contract',americanOdds:null,bidCents:'50'}}),/check constraint/);
});
await group('Duplicate quote/source identities preserve immutable observed prices and reject changed definitions',async()=>{
 const first=await rpc({action:'provider_quote_put',quote}),duplicate=await rpc({action:'provider_quote_put',quote:{...quote,observedAt:new Date(Date.parse(at)+30000).toISOString()}});assert.equal(Date.parse(duplicate.observed_at),Date.parse(first.observed_at));
 await assert.rejects(rpc({action:'provider_quote_put',quote:{...quote,americanOdds:-105}}),{code:'22023'});
 await assert.rejects(rpc({action:'provider_quote_put',quote:{...quote,eventId:'SYNTHETIC-DIFFERENT'}}),{code:'22023'});
 await assert.rejects(rpc({action:'source_put',row:{...source,source_url:'https://example.invalid/SYNTHETIC-changed'}}),{code:'22023'});
 await assert.rejects(entity('cfb_players',{id:'cfb:player:one',provider_id:'SYNTHETIC-player',name:'SYNTHETIC other person',team_id:'cfb:team:home',position:'WR'}),{code:'22023'});
 await admin(async()=>{await assert.rejects(db.query("update public.provider_market_quotes set american_odds=-105 where id=$1",[quote.id]),/immutable/);await assert.rejects(db.query('delete from public.provider_market_quotes where id=$1',[quote.id]),/immutable/);});
});
await group('Every shared quote/source/entity/cache boundary rejects credentials and private financial/owner payloads',async()=>{
 for(const key of['api_key','authorization','access_token','refresh_token','service_role_key','password','user_id','userId','bankroll','deposits','withdrawals']){
  const data={[key]:'SYNTHETIC-PRIVATE-MUST-NOT-PERSIST'};
  await assert.rejects(rpc({action:'provider_quote_put',quote:{...quote,id:'SYNTHETIC-SECRET-QUOTE-'+key,data}}),{code:'22023'});
  await assert.rejects(rpc({action:'source_put',row:{...source,id:'SYNTHETIC-SECRET-SOURCE-'+key,data}}),{code:'22023'});
  await assert.rejects(entity('cfb_conferences',{id:'cfb:secret:'+key,provider_id:'SYNTHETIC',name:'SYNTHETIC withheld',data}),{code:'22023'});
  await assert.rejects(rpc({action:'cache_put',kind:'SYNTHETIC',key:'cfb:secret:'+key,inputHash:hash,expiresAt:future,data:{sport:'CFB',...data}}),{code:'22023'});
 }
});
await group('Bounded public cache and batches are atomic, CFB-scoped and cannot nest control operations',async()=>{
 await rpc({action:'cache_put',kind:'SYNTHETIC',key:'cfb:cached:one',inputHash:hash,expiresAt:future,data:{sport:'CFB',label:'SYNTHETIC cached evidence'}});
 await assert.rejects(rpc({action:'cache_put',kind:'SYNTHETIC',key:'cfb:wrong-sport',inputHash:hash,expiresAt:future,data:{sport:'NFL'}}),/CFB|sport/i);
 await assert.rejects(rpc({action:'batch',operations:[{action:'cache_put',kind:'SYNTHETIC',key:'cfb:atomic-rollback',inputHash:hash,expiresAt:future,data:{sport:'CFB'}},{action:'unsupported'}]}),/Unsupported/);assert.equal((await db.query("select count(*)::int n from public.shared_cfb_cache where key='cfb:atomic-rollback'")).rows[0].n,0);
 for(const action of['batch','reserve_compute','complete_compute','fail_compute','status'])await assert.rejects(rpc({action:'batch',operations:[{action}]}),/Nested control/);
 await assert.rejects(rpc({action:'batch',operations:Array.from({length:101},()=>({action:'status'}))}),/1–100/);
});
await group('450MB reserve denial blocks every source/entity/quote/cache/batch write while saved reads remain available',async()=>{
 await admin(()=>db.exec("create or replace function gridiron_shared_private.has_public_storage_headroom() returns boolean language sql stable security definer set search_path='' as $$select false$$"));assert.equal((await rpc({action:'status'})).admissionAvailable,false);
 const before=await Promise.all(shared.map(count));
 const operations=[{action:'source_put',row:{...source,id:'SYNTHETIC-CAPACITY-BLOCKED'}},{action:'entity_put',table:'cfb_conferences',row:{...common,id:'cfb:capacity:blocked',provider_id:'SYNTHETIC'}},{action:'provider_quote_put',quote:{...quote,id:'SYNTHETIC-CAPACITY-QUOTE'}},{action:'cache_put',kind:'SYNTHETIC',key:'cfb:capacity:cache',inputHash:hash,expiresAt:future,data:{sport:'CFB'}},{action:'batch',operations:[{action:'cache_put',kind:'SYNTHETIC',key:'cfb:capacity:batch',inputHash:hash,expiresAt:future,data:{sport:'CFB'}}]}];
 for(const operation of operations)await assert.rejects(rpc(operation),/protect personal records|paused.*storage/i);assert.deepEqual(await Promise.all(shared.map(count)),before);
});
let first,advanced;
await group('Tiny quota metadata shares the preserved 500k UTC budget: 390k→400k→450k, with no free retry or negative counts',async()=>{
 for(const simulations of[-10000,0,9999,10001])await assert.rejects(rpc({action:'reserve_compute',inputHash:hash,simulations,lease}),/supported count/);
 assert.equal(await budget(),390000);first=await rpc({action:'reserve_compute',inputHash:hash,simulations:10000,lease});assert.equal(first.execute,true);assert.equal(await budget(),400000);
 for(const retryLease of[lease,otherLease]){const duplicate=await rpc({action:'reserve_compute',inputHash:hash,simulations:10000,lease:retryLease});assert.equal(duplicate.id,first.id);assert.equal(duplicate.execute,false);assert.equal(duplicate.status,'running');}assert.equal(await budget(),400000);
 advanced=await rpc({action:'reserve_compute',inputHash:hash,simulations:50000,lease:otherLease});assert.notEqual(advanced.id,first.id);assert.equal(advanced.execute,true);assert.equal(await budget(),450000);
 await assert.rejects(rpc({action:'reserve_compute',inputHash:'b'.repeat(64),simulations:100000,lease:thirdLease}),/Daily shared complete-game research capacity/);assert.equal(await budget(),450000);
 await admin(async()=>{await assert.rejects(db.query("update gridiron_shared_private.compute_budget set games=-1 where day=(now() at time zone 'UTC')::date"),/check constraint/);});assert.equal(await budget(),450000);
});
await group('Only exact small reservation fields are allowed; no owner, source, job output or caller-supplied UTC day enters quota metadata',async()=>{
 for(const extra of[{day:'2000-01-01'},{userId:A},{sourceUrl:'https://example.invalid/private'},{data:{sport:'CFB'}},{result:{probability:1}},{error:'SYNTHETIC'}])await assert.rejects(rpc({action:'reserve_compute',inputHash:'c'.repeat(64),simulations:10000,lease:thirdLease,...extra}),/metadata|field|supported|exact/i);
 assert.equal(await budget(),450000);await assert.rejects(rpc({action:'complete_compute',id:first.id,lease,data:{owner:A}}),/metadata|field|supported|exact/i);
 const columns=(await admin(()=>db.query("select column_name from information_schema.columns where table_schema='gridiron_shared_private' and table_name='cfb_compute_reservations' order by ordinal_position"))).rows.map(row=>row.column_name);assert.deepEqual(columns,['id','day','input_hash','simulations','status','lease','created_at','updated_at']);
});
await group('Fenced completion/failure preserves spent quota and completed/failed cache loss never re-executes uncharged work',async()=>{
 assert.ok(first&&advanced,'Initial supported reservations must have succeeded.');await assert.rejects(rpc({action:'complete_compute',id:first.id,lease:otherLease}),/Stale CFB compute lease/);
 assert.equal((await rpc({action:'complete_compute',id:first.id,lease})).status,'completed');const cached=await rpc({action:'reserve_compute',inputHash:hash,simulations:10000,lease:thirdLease});assert.equal(cached.execute,false);assert.equal(cached.status,'completed');
 await assert.rejects(rpc({action:'fail_compute',id:first.id,lease}),/Stale CFB compute lease/);await assert.rejects(rpc({action:'fail_compute',id:advanced.id,lease}),/Stale CFB compute lease/);assert.equal((await rpc({action:'fail_compute',id:advanced.id,lease:otherLease})).status,'failed');const failed=await rpc({action:'reserve_compute',inputHash:hash,simulations:50000,lease:thirdLease});assert.equal(failed.execute,false);assert.equal(failed.status,'failed');assert.equal(await budget(),450000);
 const last=await rpc({action:'reserve_compute',inputHash:'d'.repeat(64),simulations:50000,lease:thirdLease});assert.equal(last.execute,true);assert.equal(await budget(),500000);await assert.rejects(rpc({action:'reserve_compute',inputHash:'e'.repeat(64),simulations:10000,lease}),/Daily shared complete-game research capacity/);assert.equal(await budget(),500000);
});
await group('Private CFB simulation/prediction records enforce owner RLS, composite ownership FKs and prospective immutable snapshots',async()=>{
 const recordId='70000000-0000-4000-8000-000000000081',simId='80000000-0000-4000-8000-000000000081',predictionId='90000000-0000-4000-8000-000000000081';
 await owner(A);await db.query("insert into public.gridiron_records(id,kind,data)values($1,'cfb_simulation_jobs',$2::jsonb)",[recordId,JSON.stringify({sport:'CFB',label:'SYNTHETIC owned history'})]);
 await db.query("insert into public.cfb_simulation_runs(id,record_id,event_key,game_id,model_version,input_version,simulations,event_start)values($1,$2,'cfb:game:one','cfb:game:one','SYNTHETIC-CFB-V1','SYNTHETIC-INPUT',100000,$3)",[simId,recordId,future]);
 await db.query("insert into public.cfb_prediction_snapshots(id,simulation_id,event_key,market,threshold,raw_probability,captured_at,event_start,data)values($1,$2,'cfb:game:one','SYNTHETIC total',50.5,0.6,$3,$4,'{}')",[predictionId,simId,at,future]);
 await assert.rejects(db.query('update public.cfb_prediction_snapshots set raw_probability=0.9 where id=$1',[predictionId]),/permission denied|immutable/);
 await assert.rejects(db.query("insert into public.cfb_prediction_snapshots(simulation_id,event_key,market,raw_probability,calibrated_probability,captured_at,event_start,data)values($1,'cfb:game:one','SYNTHETIC',0.6,0.8,$2,$3,'{}')",[simId,at,future]),/check constraint/);
 await assert.rejects(db.query("insert into public.cfb_prediction_snapshots(simulation_id,event_key,market,raw_probability,calibrated_probability,calibration_artifact_id,calibration_status,captured_at,event_start,data)values($1,'cfb:game:one','SYNTHETIC',0.6,0.8,'cfb:model:candidate','approved',$2,$3,'{}')",[simId,at,future]),/foreign key/);
 await assert.rejects(db.query("insert into public.cfb_prediction_snapshots(simulation_id,event_key,market,raw_probability,captured_at,event_start,data)values($1,'cfb:game:one','SYNTHETIC',0.6,$2,$2,'{}')",[simId,future]),/check constraint/);
 await owner(B);for(const table of privateTables)assert.equal(await count(table),0);
 await assert.rejects(db.query("insert into public.cfb_simulation_runs(id,record_id,event_key,model_version,input_version,simulations,event_start)values('80000000-0000-4000-8000-000000000082',$1,'cfb:game:one','SYNTHETIC','SYNTHETIC',10000,$2)",[recordId,future]),/foreign key/);
 await assert.rejects(db.query("insert into public.cfb_prediction_snapshots(simulation_id,event_key,market,raw_probability,captured_at,event_start,data)values($1,'cfb:game:one','SYNTHETIC',0.6,$2,$3,'{}')",[simId,at,future]),/foreign key/);
 await assert.rejects(db.query("insert into public.cfb_prediction_snapshots(user_id,simulation_id,event_key,market,raw_probability,captured_at,event_start,data)values($1,$2,'cfb:game:one','SYNTHETIC',0.6,$3,$4,'{}')",[A,simId,at,future]),/row-level security/);
 await owner(A);assert.equal(await count('cfb_simulation_runs'),1);assert.equal(await count('cfb_prediction_snapshots'),1);assert.deepEqual((await personal('gridiron_ledger')).summary,financialBefore);
 await admin(async()=>{await assert.rejects(db.query('update public.cfb_prediction_snapshots set raw_probability=0.9 where id=$1',[predictionId]),/immutable/);await assert.rejects(db.query("update public.cfb_simulation_runs set model_version='SYNTHETIC-CHANGED' where id=$1",[simId]),/immutable/);});
});
const failed=checks.filter(check=>check.status!=='passed');console.log(JSON.stringify({scope:'SYNTHETIC disposable local PostgreSQL only',migration:upgrade,passed:checks.length-failed.length,failed:failed.length,checks},null,2));await db.close();if(failed.length)process.exitCode=1;
