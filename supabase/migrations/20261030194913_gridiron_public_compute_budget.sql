-- Guard public compute without changing private/account research workloads.
-- Cache reads are never charged to this bounded shared daily allocation.
create table gridiron_shared_private.compute_budget (
 day date primary key, games integer not null default 0 check(games>=0)
);
alter table gridiron_shared_private.compute_budget enable row level security;
revoke all on gridiron_shared_private.compute_budget from public,anon,authenticated;

alter function public.gridiron_public_write(text,jsonb) set schema gridiron_shared_private;
alter function gridiron_shared_private.gridiron_public_write(text,jsonb) rename to write_operation_v1;
revoke all on function gridiron_shared_private.write_operation_v1(text,jsonb) from public,anon,authenticated;

create function public.gridiron_public_write(token text,payload jsonb) returns jsonb
language plpgsql security definer set search_path=pg_catalog,public
as $$
declare job public.shared_nfl_jobs; result jsonb; requested integer; used integer;
 today date:=(now() at time zone 'UTC')::date;
begin
 if not gridiron_shared_private.valid_public_capability(token) then
  raise exception using errcode='42501',message='Server capability required'; end if;
 if payload->>'action' is distinct from 'job_claim' then
  return gridiron_shared_private.write_operation_v1(token,payload); end if;
 perform pg_advisory_xact_lock(hashtextextended('gridiron-public-complete-game-budget',0));
 select * into job from public.shared_nfl_jobs where id=(payload->>'id')::uuid for update;
 if job.id is null or not (job.status='queued' or (job.status='running' and job.updated_at<now()-interval '6 minutes')
   or (job.status='failed' and job.updated_at<now()-interval '2 minutes')) then return null; end if;
 requested:=coalesce((job.data->>'simulations')::integer,10000);
 if requested not in (10000,50000,100000) or payload->>'lease' is null then
  raise exception using errcode='22023',message='A supported complete-game count and lease are required'; end if;
 insert into gridiron_shared_private.compute_budget(day,games) values(today,0) on conflict(day) do nothing;
 select games into used from gridiron_shared_private.compute_budget where day=today for update;
 if used+requested>150000 then
  update public.shared_nfl_jobs set status='failed',error='Daily shared research capacity reached. Cached analyses remain available; try again tomorrow.',updated_at=now()
   where id=job.id;
  return null;
 end if;
 result:=gridiron_shared_private.write_operation_v1(token,payload);
 if result is not null then update gridiron_shared_private.compute_budget set games=games+requested where day=today; end if;
 return result;
end $$;
revoke all on function public.gridiron_public_write(text,jsonb) from public,anon,authenticated;
grant execute on function public.gridiron_public_write(text,jsonb) to anon,authenticated;
