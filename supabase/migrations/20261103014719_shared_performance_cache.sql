-- Reuse existing shared cache + lease tables. No personal rows or RLS change.
-- These entries are disposable computation caches, not prediction history.
create or replace function public.gridiron_performance_cache(token text,payload jsonb) returns jsonb
language plpgsql security definer set search_path=pg_catalog
as $$
declare k text:=payload->>'key'; act text:=payload->>'action'; c public.shared_nfl_cache;
 generation integer; until_at timestamptz; ttl integer; lease_ms integer;
begin
 if not gridiron_shared_private.valid_public_capability(token) then raise exception 'Server capability required' using errcode='42501'; end if;
 if jsonb_typeof(payload) is distinct from 'object' or octet_length(payload::text)>750000 or k !~ '^(cfb_prepare|market_board|auto_props|cfb_status|cfb_schedule):[a-f0-9]{64}$' or k is null then raise exception 'Bounded public compute cache required' using errcode='22023'; end if;
 if act='acquire' then
  select * into c from public.shared_nfl_cache where kind='performance_cache' and key=k;
  if c.expires_at>clock_timestamp() and c.data ? 'value' then return jsonb_build_object('state','hit','value',c.data->'value','expiresAt',c.expires_at);end if;
  lease_ms:=least(300000,greatest(1000,coalesce((payload->>'leaseMs')::integer,120000)));
  insert into gridiron_shared_private.public_rate_limits(key,count,expires_at) values('perf-cache:'||k,1,clock_timestamp()+lease_ms*interval '1 millisecond')
   on conflict(key) do update set count=public_rate_limits.count+1,expires_at=excluded.expires_at where public_rate_limits.expires_at<=clock_timestamp()
   returning count,expires_at into generation,until_at;
  if generation is not null then
   -- Another producer may have committed after our first read and before lease acquisition.
   select * into c from public.shared_nfl_cache where kind='performance_cache' and key=k;
   if c.expires_at>clock_timestamp() and c.data ? 'value' then
    update gridiron_shared_private.public_rate_limits set expires_at=clock_timestamp() where key='perf-cache:'||k;
    return jsonb_build_object('state','hit','value',c.data->'value','expiresAt',c.expires_at);
   end if;
   return jsonb_build_object('state','claimed','generation',generation,'expiresAt',until_at);
  end if;
  select expires_at into until_at from gridiron_shared_private.public_rate_limits where key='perf-cache:'||k;
  return jsonb_build_object('state','wait','retryAt',until_at);
 elsif act in ('finish','fail') then
  select count,expires_at into generation,until_at from gridiron_shared_private.public_rate_limits where key='perf-cache:'||k for update;
  if generation is null or payload->>'generation' is null or generation is distinct from (payload->>'generation')::integer or until_at<=clock_timestamp() then return jsonb_build_object('accepted',false);end if;
  if act='fail' then
   update gridiron_shared_private.public_rate_limits set expires_at=clock_timestamp()+interval '30 seconds' where key='perf-cache:'||k;
   return jsonb_build_object('accepted',true);
  end if;
  if jsonb_typeof(payload->'value') is distinct from 'object' or payload->'value'->>'encoding' is distinct from 'gzip-base64-v1' or payload->'value'->>'sha256' !~ '^[a-f0-9]{64}$' or (payload->'value'->>'bytes')::integer not between 0 and 16000000 then raise exception 'Verified bounded cache envelope required' using errcode='22023';end if;
  ttl:=least(600000,greatest(1000,(payload->>'ttlMs')::integer));
  -- Bounded population. Never evict research, snapshots or accounting data.
  perform pg_advisory_xact_lock(hashtext('gridiron-performance-cache-population'));
  if not exists(select 1 from public.shared_nfl_cache where kind='performance_cache' and key=k) and (select count(*) from public.shared_nfl_cache where kind='performance_cache')>=64 then
   delete from public.shared_nfl_cache where kind='performance_cache' and key=(select key from public.shared_nfl_cache where kind='performance_cache' order by expires_at limit 1);
  end if;
  until_at:=clock_timestamp()+ttl*interval '1 millisecond';
  insert into public.shared_nfl_cache(kind,key,data,input_hash,expires_at) values('performance_cache',k,jsonb_build_object('value',payload->'value'),payload->'value'->>'sha256',until_at)
   on conflict(kind,key) do update set data=excluded.data,input_hash=excluded.input_hash,expires_at=excluded.expires_at,updated_at=clock_timestamp();
  update gridiron_shared_private.public_rate_limits set expires_at=clock_timestamp() where key='perf-cache:'||k;
  return jsonb_build_object('accepted',true,'expiresAt',until_at);
 end if;
 raise exception 'Unsupported cache operation' using errcode='22023';
end $$;
revoke all on function public.gridiron_performance_cache(text,jsonb) from public,anon,authenticated;
grant execute on function public.gridiron_performance_cache(text,jsonb) to anon,authenticated;
comment on function public.gridiron_performance_cache(text,jsonb) is 'Capability-only bounded public research cache, distributed leases and generation fencing. Existing private RLS and immutable history are unchanged.';

-- Existing latest-run reads used a sort; scheduled status reads need metadata only.
create index if not exists shared_prop_runs_created_id on public.shared_prop_runs(created_at desc,id);
