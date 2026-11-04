-- Read existing append-only research versions. No user or financial table changes.
create index automatic_prop_history_page on gridiron_shared_private.automatic_prop_versions(job_id,id desc) where evidence_hash like 'selections:%';
create function public.gridiron_auto_prop_history(token text,job_id text,before_id bigint default null) returns jsonb
language plpgsql security definer set search_path='' as $$
declare result jsonb;
begin
 if not gridiron_shared_private.valid_public_capability(token) then raise exception 'Server capability required' using errcode='42501';end if;
 if job_id is null or job_id !~ '^[a-f0-9]{64}$' or before_id is not null and before_id<1 then raise exception 'Invalid research history page';end if;
 select coalesce(jsonb_agg(to_jsonb(page) order by page.id desc),'[]'::jsonb) into result from (
  select v.id,v.created_at,v.result_ref from gridiron_shared_private.automatic_prop_versions v
  where v.job_id=gridiron_auto_prop_history.job_id and v.evidence_hash like 'selections:%' and (before_id is null or v.id<before_id)
  order by v.id desc limit 8
 )page;
 return result;
end $$;
revoke all on function public.gridiron_auto_prop_history(text,text,bigint) from public;
grant execute on function public.gridiron_auto_prop_history(text,text,bigint) to anon,authenticated,service_role;
-- Rollback: stop using the new read API. Preserve all existing version rows and indexes.
