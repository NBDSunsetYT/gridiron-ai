-- Additive operational queue. No changes to predictions, objects, wallets or RLS.
create table gridiron_shared_private.compute_jobs (
 id text primary key check(id ~ '^[a-f0-9]{64}$'), task jsonb not null,
 status text not null default 'queued' check(status in ('queued','running','completed','delayed')),
 attempts integer not null default 0, generation integer not null default 0,
 due_at timestamptz not null default now(), lease_until timestamptz,
 created_at timestamptz not null default now(), updated_at timestamptz not null default now(),
 budget_day date, error_code text, cpu_ms bigint not null default 0
);
alter table gridiron_shared_private.compute_jobs enable row level security;
revoke all on gridiron_shared_private.compute_jobs from public,anon,authenticated;
create index compute_jobs_due on gridiron_shared_private.compute_jobs(due_at,created_at) where status in ('queued','delayed');
-- Extend the existing daily budget; its original NFL games counter is unchanged.
alter table gridiron_shared_private.compute_budget
 add column controlled_jobs integer not null default 0,
 add column trials integer not null default 0,
 add column reserved_seconds integer not null default 0,
 add column measured_cpu_ms bigint not null default 0;
create or replace function public.gridiron_compute_jobs(token text,payload jsonb) returns jsonb
language plpgsql security definer set search_path=pg_catalog as $$
declare act text:=payload->>'action'; k text:=payload->>'id'; t jsonb:=payload->'task';
 j gridiron_shared_private.compute_jobs; b gridiron_shared_private.compute_budget;
 needed_trials integer; cost integer; retry_seconds integer; current_day date:=(clock_timestamp() at time zone 'UTC')::date;
begin
 if not gridiron_shared_private.valid_public_capability(token) then raise exception 'Server capability required' using errcode='42501';end if;
 if jsonb_typeof(payload) is distinct from 'object' or octet_length(payload::text)>12000 then raise exception 'Bounded task required' using errcode='22023';end if;
 if act='enqueue' then
  if k is null or k !~ '^[a-f0-9]{64}$' or jsonb_typeof(t) is distinct from 'object' or t->>'kind' is null or t->>'kind' not in ('game','probability','prop_scan','maintenance') or payload->>'version' is distinct from 'bounded-compute-1' then raise exception 'Recognized task required' using errcode='22023';end if;
  if t->>'kind'='game' and (t->>'sport' not in ('NFL','CFB','NBA') or t->>'gameId' is null or length(t->>'gameId')>100 or (t->>'simulations')::integer not in (10000,50000,100000)) then raise exception 'Supported game required' using errcode='22023';end if;
  if t->>'kind'='probability' and (jsonb_typeof(t->'request') is distinct from 'object' or (t->'request'->>'simulations')::integer not in (10000,50000,100000)) then raise exception 'Supported probability request required' using errcode='22023';end if;
  perform pg_advisory_xact_lock(hashtext('gridiron-bounded-compute'));
  select * into j from gridiron_shared_private.compute_jobs where id=k;
  if j.id is not null and j.task is distinct from t then raise exception 'Task identity collision' using errcode='22023';end if;
  if j.id is null then
   if (select count(*) from gridiron_shared_private.compute_jobs where status<>'completed')>=128 then return jsonb_build_object('id',k,'status','delayed','reason','queue_capacity','retryAfterSeconds',300);end if;
   insert into gridiron_shared_private.compute_jobs(id,task) values(k,t) returning * into j;
  elsif j.status='completed' and j.due_at<=clock_timestamp() then
   update gridiron_shared_private.compute_jobs set status='queued',updated_at=clock_timestamp(),attempts=0,error_code=null where id=k returning * into j;
  end if;
  return jsonb_build_object('id',j.id,'status',j.status,'retryAt',j.due_at,'retryAfterSeconds',30);
 elsif act='claim' then
  perform pg_advisory_xact_lock(hashtext('gridiron-bounded-compute'));
  if exists(select 1 from gridiron_shared_private.compute_jobs where status='running' and lease_until>clock_timestamp()) then return null;end if;
  -- Expired work must back off; fencing rejects the previous process's writes.
  update gridiron_shared_private.compute_jobs set status='delayed',due_at=clock_timestamp()+interval '5 minutes',error_code='worker_lease_expired',updated_at=clock_timestamp() where status='running' and lease_until<=clock_timestamp();
  select * into j from gridiron_shared_private.compute_jobs where status in ('queued','delayed') and due_at<=clock_timestamp() and attempts<5 order by created_at for update skip locked limit 1;
  if j.id is null then return null;end if;
  needed_trials:=case when j.task->>'kind'='game' then (j.task->>'simulations')::integer when j.task->>'kind'='probability' then (j.task->'request'->>'simulations')::integer * case when j.task->'request'->'target'->>'type'='combination' then jsonb_array_length(j.task->'request'->'target'->'legs')+1 else 1 end when j.task->>'kind'='prop_scan' then 10000 else 10000 end;
  cost:=least(300,greatest(30,coalesce((payload->>'timeoutSeconds')::integer,300)));
  insert into gridiron_shared_private.compute_budget(day) values(current_day) on conflict do nothing;
  select * into b from gridiron_shared_private.compute_budget where day=current_day for update;
  -- Worst-case reservations remain charged after crashes. No caller can raise limits.
  if b.controlled_jobs>=6 or b.trials+needed_trials>100000 or b.reserved_seconds+cost>1800 then return null;end if;
  update gridiron_shared_private.compute_budget set controlled_jobs=controlled_jobs+1,trials=compute_budget.trials+needed_trials,reserved_seconds=reserved_seconds+cost where day=current_day;
  update gridiron_shared_private.compute_jobs set status='running',budget_day=current_day,attempts=attempts+1,generation=generation+1,lease_until=clock_timestamp()+(cost+30)*interval '1 second',updated_at=clock_timestamp() where id=j.id returning * into j;
  return jsonb_build_object('id',j.id,'task',j.task,'generation',j.generation,'timeoutSeconds',cost,'reservedTrials',needed_trials);
 elsif act='finish' then
  select * into j from gridiron_shared_private.compute_jobs where id=k for update;
  if j.id is null or j.status<>'running' or j.generation is distinct from (payload->>'generation')::integer or j.lease_until<=clock_timestamp() then return jsonb_build_object('accepted',false);end if;
  retry_seconds:=least(3600,(60*power(2,least(6,j.attempts)))::integer);
  update gridiron_shared_private.compute_jobs set status=case when payload->>'success'='true' then 'completed' else 'delayed' end,due_at=clock_timestamp()+(case when payload->>'success'='true' then case when j.task->>'kind'='maintenance' then 3600 else 900 end else retry_seconds end)*interval '1 second',lease_until=null,error_code=case when payload->>'success'='true' then null else 'worker_task_failed' end,cpu_ms=cpu_ms+least(3600000,greatest(0,coalesce((payload->>'cpuMs')::bigint,0))),updated_at=clock_timestamp() where id=k;
  update gridiron_shared_private.compute_budget set measured_cpu_ms=measured_cpu_ms+least(3600000,greatest(0,coalesce((payload->>'cpuMs')::bigint,0))) where day=j.budget_day;
  return jsonb_build_object('accepted',true);
 elsif act='status' then
  if k is not null then select * into j from gridiron_shared_private.compute_jobs where id=k;return case when j.id is null then null else jsonb_build_object('id',j.id,'status',j.status,'retryAt',j.due_at,'updatedAt',j.updated_at,'reasonCode',j.error_code,'attempts',j.attempts) end;end if;
  return jsonb_build_object('role','cache_and_queue_only','concurrency',1,'dailyJobLimit',6,'dailyTrialLimit',100000,'dailyWorstCaseSeconds',1800,'budget',coalesce((select to_jsonb(q) from gridiron_shared_private.compute_budget q where day=current_day),'{}'::jsonb),'jobs',(select coalesce(jsonb_object_agg(status,n),'{}'::jsonb) from (select status,count(*) n from gridiron_shared_private.compute_jobs group by status) s));
 end if;
 raise exception 'Unsupported compute operation' using errcode='22023';
end $$;
revoke all on function public.gridiron_compute_jobs(text,jsonb) from public,anon,authenticated;
grant execute on function public.gridiron_compute_jobs(text,jsonb) to anon,authenticated;
comment on function public.gridiron_compute_jobs(text,jsonb) is 'Server-capability public research queue. No personal data; global concurrency, daily admission and lease fencing. Models never run in SQL.';
