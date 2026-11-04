-- Preserve every existing version. A read-only preflight prevents duplicate object uploads.
create or replace function public.gridiron_auto_props(token text,payload jsonb) returns jsonb
language plpgsql security definer set search_path=pg_catalog,public,gridiron_shared_private as $$
declare item jsonb; job gridiron_shared_private.automatic_prop_jobs; answer jsonb;
begin
 if not exists(select 1 from gridiron_shared_private.capabilities c where c.name='public_nfl_ingestion' and c.token_sha256=encode(sha256(convert_to(token,'UTF8')),'hex')) then raise exception 'Server capability required' using errcode='42501';end if;
 if pg_column_size(payload)>32768 then raise exception 'Research queue payload too large';end if;
 case payload->>'action'
 when 'enqueue' then
  if jsonb_array_length(payload->'jobs')>20 then raise exception 'Bounded research batch required';end if;
  for item in select value from jsonb_array_elements(payload->'jobs') loop
   if (item->>'kickoff')::timestamptz<=now() then continue;end if;
   insert into gridiron_shared_private.automatic_prop_jobs(id,sport,event_id,kickoff,input_hash)
   values(item->>'id',item->>'sport',item->>'eventId',(item->>'kickoff')::timestamptz,item->>'inputHash')
   on conflict(id) do update set kickoff=excluded.kickoff,input_hash=excluded.input_hash,
    status=case when automatic_prop_jobs.status='running' and automatic_prop_jobs.lease_until>now() then 'running' else 'queued' end,
    due_at=now(),updated_at=now()
   where automatic_prop_jobs.input_hash<>excluded.input_hash or (automatic_prop_jobs.status<>'running' and automatic_prop_jobs.due_at<=now());
  end loop;
  return jsonb_build_object('queued',true);
 when 'read' then
  if jsonb_array_length(payload->'ids')>20 then raise exception 'Bounded research read required';end if;
  select coalesce(jsonb_agg(to_jsonb(j)-'lease'),'[]'::jsonb) into answer from gridiron_shared_private.automatic_prop_jobs j where id in(select jsonb_array_elements_text(payload->'ids'));
  return answer;
 when 'claim' then
  select * into job from gridiron_shared_private.automatic_prop_jobs j where j.kickoff>now() and j.due_at<=now() and (j.status in ('queued','delayed') or j.status='running' and j.lease_until<now())
  order by j.kickoff,j.due_at for update skip locked limit 1;
  if not found then return null;end if;
  update gridiron_shared_private.automatic_prop_jobs set status='running',lease=(payload->>'lease')::uuid,lease_until=now()+interval '5 minutes',attempts=attempts+1,updated_at=now() where id=job.id returning * into job;
  return to_jsonb(job);
 when 'snapshot' then
  select * into job from gridiron_shared_private.automatic_prop_jobs where id=payload->>'id' and status='ready' and input_hash=payload->>'inputHash';
  if not found then return jsonb_build_object('accepted',false);end if;
  if exists(select 1 from gridiron_shared_private.automatic_prop_versions where job_id=job.id and evidence_hash=payload->>'evidenceHash') then return jsonb_build_object('accepted',true,'duplicate',true);end if;
  if payload->'resultRef' is null then return jsonb_build_object('accepted',true,'duplicate',false,'needsObject',true);end if;
  if jsonb_typeof(payload->'resultRef')<>'object' then raise exception 'Immutable snapshot reference required';end if;
  insert into gridiron_shared_private.automatic_prop_versions(job_id,evidence_hash,result_ref) values(job.id,payload->>'evidenceHash',payload->'resultRef') on conflict(job_id,evidence_hash) do nothing;
  return jsonb_build_object('accepted',true);
 when 'finish' then
  select * into job from gridiron_shared_private.automatic_prop_jobs where id=payload->>'id' for update;
  if not found or job.lease is distinct from (payload->>'lease')::uuid or job.lease_until<now() then return jsonb_build_object('accepted',false);end if;
  -- Input changes during a lease must queue another run, never publish stale output.
  if job.input_hash is distinct from payload->>'inputHash' then
   update gridiron_shared_private.automatic_prop_jobs set status='queued',lease=null,lease_until=null,due_at=now(),updated_at=now() where id=job.id;
   return jsonb_build_object('accepted',false);
  end if;
  if payload->'resultRef' is not null and jsonb_typeof(payload->'resultRef')='object' then
   insert into gridiron_shared_private.automatic_prop_versions(job_id,evidence_hash,result_ref) values(job.id,payload->>'evidenceHash',payload->'resultRef') on conflict(job_id,evidence_hash) do nothing;
   update gridiron_shared_private.automatic_prop_jobs set status='ready',result_ref=payload->'resultRef',reason=null,lease=null,lease_until=null,attempts=0,due_at=least(kickoff,now()+interval '15 minutes'),updated_at=now() where id=job.id;
  else
   update gridiron_shared_private.automatic_prop_jobs set status='delayed',reason=left(payload->>'reason',600),lease=null,lease_until=null,due_at=now()+make_interval(secs=>least(3600,30*power(2,least(attempts,7))::integer)),updated_at=now() where id=job.id;
  end if;
  return jsonb_build_object('accepted',true);
 else raise exception 'Unsupported automatic research operation';
 end case;
end $$;
revoke all on function public.gridiron_auto_props(text,jsonb) from public;
grant execute on function public.gridiron_auto_props(text,jsonb) to anon,authenticated,service_role;
