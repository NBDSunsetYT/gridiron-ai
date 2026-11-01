import{PGlite}from'@electric-sql/pglite';import{readdirSync,readFileSync}from'node:fs';import assert from'node:assert/strict';
const db=new PGlite();await db.exec("create role anon;create role authenticated;create role service_role bypassrls;create schema auth;create table auth.users(id uuid primary key,email text);create table auth.sessions(id uuid primary key,user_id uuid references auth.users(id));create function auth.uid()returns uuid language sql stable as $$select null::uuid$$;create function auth.jwt()returns jsonb language sql stable as $$select '{}'::jsonb$$;");
for(const f of readdirSync(new URL('../migrations/',import.meta.url)).filter(x=>x.endsWith('.sql')).sort())await db.exec(readFileSync(new URL('../migrations/'+f,import.meta.url),'utf8'));

const cap='SYNTHETIC-AUTO-QUEUE-CAPABILITY-NOT-A-KEY';await db.query("insert into gridiron_shared_private.capabilities(name,token_sha256)values('public_nfl_ingestion',encode(sha256(convert_to($1,'UTF8')),'hex'))",[cap]);
const call=async(payload)=>(await db.query('select public.gridiron_auto_props($1,$2::jsonb) value',[cap,JSON.stringify(payload)])).rows[0].value;
await db.exec('set role anon');await assert.rejects(db.query('select * from gridiron_shared_private.automatic_prop_jobs'),/permission denied/);
await assert.rejects(db.query('select public.gridiron_auto_props($1,$2::jsonb)',['SYNTHETIC-WRONG','{"action":"claim"}']),/Server capability/);
const a='a'.repeat(64),b='b'.repeat(64),lease='11111111-1111-4111-8111-111111111111',other='22222222-2222-4222-8222-222222222222';
await call({action:'enqueue',jobs:[{id:a,sport:'NFL',eventId:'123',kickoff:'2099-02-01',inputHash:'first'},{id:b,sport:'CFB',eventId:'123',kickoff:'2099-01-01',inputHash:'first'}]});
assert.equal((await call({action:'claim',lease})).id,b,'earliest kickoff has priority');assert.equal((await call({action:'claim',lease:other})).id,a);assert.equal(await call({action:'claim',lease}),null,'active leases prevent duplicate claims');
assert.equal((await call({action:'finish',id:b,lease:other,inputHash:'first'})).accepted,false,'wrong lease fenced');
await call({action:'enqueue',jobs:[{id:b,sport:'CFB',eventId:'123',kickoff:'2099-01-01',inputHash:'changed'}]});
assert.equal((await call({action:'finish',id:b,lease,inputHash:'first',evidenceHash:'x',resultRef:{synthetic:true}})).accepted,false,'changed inputs cannot publish old evidence');
assert.equal((await call({action:'claim',lease:other})).id,b);
await call({action:'finish',id:b,lease:other,inputHash:'changed',evidenceHash:'e',resultRef:{synthetic:true}});
const read=await call({action:'read',ids:[b]});assert.equal(read[0].status,'ready');assert.equal(read[0].lease,undefined);assert.ok(read[0].result_ref);
await call({action:'finish',id:a,lease:other,inputHash:'first',reason:'SYNTHETIC provider delayed'});const delayed=(await call({action:'read',ids:[a]}))[0];assert.equal(delayed.status,'delayed');assert.ok(new Date(delayed.due_at)>new Date());
await db.exec('reset role');assert.equal((await db.query('select count(*) n from gridiron_shared_private.automatic_prop_versions')).rows[0].n,1);console.log('PASS automatic research queue: private isolation, capability denial, priority, leasing, changed-input fencing, immutable versions and retry backoff');await db.close();
