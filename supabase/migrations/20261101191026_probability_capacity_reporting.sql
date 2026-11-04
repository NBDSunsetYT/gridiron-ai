-- Read-only capacity reporting; never resets usage, raises limits or edits user data.
create function public.gridiron_probability_capacity(token text) returns jsonb
language plpgsql security definer set search_path='' as $$
declare today date:=(now() at time zone 'UTC')::date;used integer;
begin
 if not gridiron_shared_private.valid_public_capability(token) then raise exception 'Server capability required' using errcode='42501';end if;
 select games into used from gridiron_shared_private.compute_budget where day=today;
 return jsonb_build_object('used',coalesce(used,0),'limit',500000,'backgroundLimit',300000,'resetsAt',((today+1)::timestamp at time zone 'UTC'));
end $$;
revoke all on function public.gridiron_probability_capacity(text) from public;
grant execute on function public.gridiron_probability_capacity(text) to anon,authenticated,service_role;
-- Reversal removes only this new function. Keep all existing data and usage rows.
