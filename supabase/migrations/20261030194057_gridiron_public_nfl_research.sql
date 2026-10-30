-- Additive shared research only. Existing 47 user-owned tables and policies are untouched.
-- Public reads contain published NFL evidence; all writes require a dedicated
-- high-entropy server capability. No service-role key is shipped to a client.
create schema if not exists gridiron_shared_private;
revoke all on schema gridiron_shared_private from public, anon, authenticated;

create table if not exists gridiron_shared_private.capabilities (
 name text primary key, token_sha256 text not null check(token_sha256 ~ '^[a-f0-9]{64}$'),
 created_at timestamptz not null default now()
);
create table if not exists gridiron_shared_private.public_rate_limits (
 key text primary key check(length(key) between 1 and 200), count integer not null,
 expires_at timestamptz not null
);
alter table gridiron_shared_private.capabilities enable row level security;
alter table gridiron_shared_private.public_rate_limits enable row level security;
revoke all on all tables in schema gridiron_shared_private from public, anon, authenticated;

create table if not exists public.shared_nfl_cache (
 kind text not null check(kind ~ '^[a-z_]{1,40}$'), key text not null check(length(key) between 1 and 200),
 data jsonb not null check(jsonb_typeof(data)='object'), input_hash text,
 updated_at timestamptz not null default now(), expires_at timestamptz,
 primary key(kind,key)
);
create table if not exists public.shared_nfl_jobs (
 id uuid primary key default gen_random_uuid(), game_id text not null check(length(game_id) between 1 and 100),
 input_hash text not null check(length(input_hash) between 1 and 200),
 status text not null default 'queued' check(status in ('queued','running','completed','failed')),
 data jsonb not null default '{}'::jsonb check(jsonb_typeof(data)='object'), result jsonb,
 error text, lease uuid, created_at timestamptz not null default now(), updated_at timestamptz not null default now(),
 unique(game_id,input_hash)
);
create table if not exists public.shared_nfl_snapshots (
 id uuid primary key default gen_random_uuid(), game_id text not null, input_hash text not null,
 data jsonb not null, created_at timestamptz not null default now()
);
create index if not exists shared_nfl_jobs_updated_idx on public.shared_nfl_jobs(status,updated_at);
create index if not exists shared_nfl_snapshots_game_idx on public.shared_nfl_snapshots(game_id,created_at desc);
alter table public.shared_nfl_cache enable row level security;
alter table public.shared_nfl_jobs enable row level security;
alter table public.shared_nfl_snapshots enable row level security;
revoke all on public.shared_nfl_cache,public.shared_nfl_jobs,public.shared_nfl_snapshots from public,anon,authenticated;
grant select on public.shared_nfl_cache,public.shared_nfl_jobs,public.shared_nfl_snapshots to anon,authenticated;
create policy shared_nfl_public_cache_read on public.shared_nfl_cache for select to anon,authenticated
 using(kind in ('schedule','detail','analysis','summary','status','performance'));
create policy shared_nfl_public_job_read on public.shared_nfl_jobs for select to anon,authenticated using(true);
create policy shared_nfl_public_snapshot_read on public.shared_nfl_snapshots for select to anon,authenticated using(true);

create or replace function gridiron_shared_private.valid_public_capability(token text) returns boolean
language sql stable security definer set search_path=pg_catalog
as $$ select length(coalesce(token,'')) between 40 and 200 and exists(
 select 1 from gridiron_shared_private.capabilities c where c.name='public_nfl_ingestion'
 and c.token_sha256=encode(sha256(convert_to(token,'UTF8')),'hex')) $$;
revoke all on function gridiron_shared_private.valid_public_capability(text) from public,anon,authenticated;

-- Intentionally capability-authenticated service RPC, never a user-auth bypass.
-- The definer may write only these new shared tables, not any personal record.
create or replace function public.gridiron_public_write(token text,payload jsonb) returns jsonb
language plpgsql security definer set search_path=pg_catalog,public
as $$
declare action text:=payload->>'action'; row_job public.shared_nfl_jobs; row_cache public.shared_nfl_cache;
 rate_count integer; rate_until timestamptz; window_ms integer; request_limit integer; affected integer;
begin
 if not gridiron_shared_private.valid_public_capability(token) then raise exception using errcode='42501',message='Server capability required'; end if;
 if payload is null or jsonb_typeof(payload)<>'object' or octet_length(payload::text)>25000000 then
  raise exception using errcode='22023',message='Bounded JSON operation required'; end if;
 if action='cache_put' then
  insert into public.shared_nfl_cache(kind,key,data,input_hash,expires_at)
   values(payload->>'kind',payload->>'key',payload->'data',payload->>'inputHash',(payload->>'expiresAt')::timestamptz)
   on conflict(kind,key) do update set data=excluded.data,input_hash=excluded.input_hash,expires_at=excluded.expires_at,updated_at=now()
   returning * into row_cache;
  return to_jsonb(row_cache);
 elsif action='job_enqueue' then
  insert into public.shared_nfl_jobs(id,game_id,input_hash,data)
   values(coalesce((payload->>'id')::uuid,gen_random_uuid()),payload->>'gameId',payload->>'inputHash',coalesce(payload->'data','{}'))
   on conflict(game_id,input_hash) do nothing;
  select * into row_job from public.shared_nfl_jobs where game_id=payload->>'gameId' and input_hash=payload->>'inputHash';
  return to_jsonb(row_job);
 elsif action='job_claim' then
  update public.shared_nfl_jobs set status='running',lease=(payload->>'lease')::uuid,error=null,updated_at=now()
   where id=(payload->>'id')::uuid and (status='queued' or (status='running' and updated_at<now()-interval '6 minutes')
     or (status='failed' and updated_at<now()-interval '2 minutes')) returning * into row_job;
  return to_jsonb(row_job);
 elsif action='job_complete' then
  if jsonb_typeof(payload->'result') is distinct from 'object' then raise exception using errcode='22023',message='Complete result required'; end if;
  update public.shared_nfl_jobs set status='completed',result=payload->'result',error=null,updated_at=now()
   where id=(payload->>'id')::uuid and status='running' and lease=(payload->>'lease')::uuid returning * into row_job;
  if row_job.id is null then raise exception using errcode='40001',message='Stale worker lease'; end if;
  insert into public.shared_nfl_snapshots(game_id,input_hash,data)
   values(row_job.game_id,row_job.input_hash,jsonb_build_object('jobId',row_job.id,'assumptions',row_job.data,'result',row_job.result));
  return to_jsonb(row_job);
 elsif action='job_fail' then
  update public.shared_nfl_jobs set status='failed',error=left(payload->>'error',1000),updated_at=now()
   where id=(payload->>'id')::uuid and status='running' and lease=(payload->>'lease')::uuid returning * into row_job;
  if row_job.id is null then raise exception using errcode='40001',message='Stale worker lease'; end if;
  return to_jsonb(row_job);
 elsif action='invalidate_game' then
  update public.shared_nfl_cache set expires_at=least(coalesce(expires_at,now()),now())
   where key=payload->>'gameId' and kind in ('analysis','detail','summary');
  get diagnostics affected=row_count;
  return jsonb_build_object('invalidated',affected,'snapshotsPreserved',true);
 elsif action='rate_limit' then
  window_ms:=least(3600000,greatest(1000,(payload->>'windowMs')::integer));
  request_limit:=least(1200,greatest(1,(payload->>'limit')::integer));
  delete from gridiron_shared_private.public_rate_limits where expires_at<now()-interval '1 hour';
  insert into gridiron_shared_private.public_rate_limits(key,count,expires_at)
   values(payload->>'key',1,now()+window_ms*interval '1 millisecond')
   on conflict(key) do update set count=case when public_rate_limits.expires_at<=now() then 1 else public_rate_limits.count+1 end,
    expires_at=case when public_rate_limits.expires_at<=now() then excluded.expires_at else public_rate_limits.expires_at end
   returning count,expires_at into rate_count,rate_until;
  return jsonb_build_object('allowed',rate_count<=request_limit,'retryAfterSeconds',greatest(1,ceil(extract(epoch from rate_until-now()))));
 else raise exception using errcode='22023',message='Unsupported shared research operation'; end if;
end $$;
revoke all on function public.gridiron_public_write(text,jsonb) from public,anon,authenticated;
grant execute on function public.gridiron_public_write(text,jsonb) to anon,authenticated;

create or replace function public.gridiron_public_artifact(token text,kind text,key text) returns jsonb
language plpgsql security definer set search_path=pg_catalog,public
as $$ declare value jsonb; begin
 if not gridiron_shared_private.valid_public_capability(token) then raise exception using errcode='42501',message='Server capability required'; end if;
 select to_jsonb(c) into value from public.shared_nfl_cache c where c.kind=gridiron_public_artifact.kind and c.key=gridiron_public_artifact.key;
 return value;
end $$;
revoke all on function public.gridiron_public_artifact(text,text,text) from public,anon,authenticated;
grant execute on function public.gridiron_public_artifact(text,text,text) to anon,authenticated;

comment on function public.gridiron_public_write(text,jsonb) is 'Server-only shared NFL ingestion capability. Never pass token to browsers. Does not access user-owned records.';
