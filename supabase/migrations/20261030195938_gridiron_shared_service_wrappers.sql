-- Exposed RPCs are invokers. Narrow privileged implementations live in the
-- unexposed schema, authenticate the server capability, and cannot touch any
-- personal account table. Schema USAGE never grants a table read or a token.
alter function public.gridiron_public_write(text,jsonb) set schema gridiron_shared_private;
alter function gridiron_shared_private.gridiron_public_write(text,jsonb) rename to write_operation;
alter function public.gridiron_public_artifact(text,text,text) set schema gridiron_shared_private;
alter function gridiron_shared_private.gridiron_public_artifact(text,text,text) rename to read_artifact;
create or replace function gridiron_shared_private.read_artifact(token text,kind text,key text) returns jsonb
language plpgsql security definer set search_path=pg_catalog,public
as $$declare value jsonb;begin
 if not gridiron_shared_private.valid_public_capability(token) then raise exception using errcode='42501',message='Server capability required'; end if;
 select to_jsonb(c) into value from public.shared_nfl_cache c where c.kind=$2 and c.key=$3;
 return value;
end$$;
revoke all on function gridiron_shared_private.write_operation(text,jsonb),gridiron_shared_private.read_artifact(text,text,text) from public,anon,authenticated;
grant usage on schema gridiron_shared_private to anon,authenticated;
grant execute on function gridiron_shared_private.write_operation(text,jsonb),gridiron_shared_private.read_artifact(text,text,text) to anon,authenticated;

create function public.gridiron_public_write(token text,payload jsonb) returns jsonb
language sql security invoker set search_path=''
as $$select gridiron_shared_private.write_operation(token,payload)$$;
create function public.gridiron_public_artifact(token text,kind text,key text) returns jsonb
language sql security invoker set search_path=''
as $$select gridiron_shared_private.read_artifact(token,kind,key)$$;
revoke all on function public.gridiron_public_write(text,jsonb),public.gridiron_public_artifact(text,text,text) from public,anon,authenticated;
grant execute on function public.gridiron_public_write(text,jsonb),public.gridiron_public_artifact(text,text,text) to anon,authenticated;

-- Explicit deny policies document the intended client boundary in advisors.
-- These do not grant table privileges or alter any existing personal policy.
create policy no_client_capability_access on gridiron_shared_private.capabilities for all to anon,authenticated using(false) with check(false);
create policy no_client_rate_limit_access on gridiron_shared_private.public_rate_limits for all to anon,authenticated using(false) with check(false);
create policy no_client_compute_budget_access on gridiron_shared_private.compute_budget for all to anon,authenticated using(false) with check(false);
