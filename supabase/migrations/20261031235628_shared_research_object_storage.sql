-- Existing records are unchanged. Bulky new public results live in immutable private
-- object storage; existing NFL job/snapshot tables retain compact searchable metadata.
create function public.gridiron_shared_storage_authorized(token text) returns boolean
language sql security definer set search_path='' as $$select gridiron_shared_private.valid_public_capability(token)$$;
revoke all on function public.gridiron_shared_storage_authorized(text) from public,anon,authenticated;
grant execute on function public.gridiron_shared_storage_authorized(text) to service_role;
-- Bulk market ingestion keeps its existing 450MB ceiling. Only bounded critical
-- NFL operational metadata can use the next20MB; at least30MB remains reserved
-- below the existing project's500MB free database limit. No billing change.
create function gridiron_shared_private.can_admit_nfl_metadata(payload jsonb) returns boolean
language sql set search_path='' as $$select gridiron_shared_private.has_public_storage_headroom() or (pg_database_size(current_database())<470000000 and octet_length(payload::text)<=65536)$$;
revoke all on function gridiron_shared_private.can_admit_nfl_metadata(jsonb) from public,anon,authenticated;
do $$
declare definition text;old_clause text:=$old$action in ('job_enqueue','job_complete') and not gridiron_shared_private.has_public_storage_headroom()$old$;
begin
 select pg_get_functiondef('gridiron_shared_private.write_operation_v1(text,jsonb)'::regprocedure) into definition;
 if (length(definition)-length(replace(definition,old_clause,'')))/length(old_clause)<>1 then raise exception 'Unexpected NFL admission function; no existing data was changed';end if;
 execute replace(definition,old_clause,$new$action in ('job_enqueue','job_complete') and not gridiron_shared_private.can_admit_nfl_metadata(payload)$new$);
end $$;
-- Reversal: replace the new admission clause above with the old clause. Keep all
-- rows and stored objects. Older application versions cannot hydrate new object
-- pointers, so code rollback must retain the object reader until records migrate.
