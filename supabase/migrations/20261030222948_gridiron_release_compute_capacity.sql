-- Preserve every reservation and prior snapshot. The initial v6 full-slate
-- upgrade and explicit 100k research mode share a bounded daily admission pool.
-- This changes no hosting plan, paid resource, user record or historical usage.
do $$
declare definition text;old_guard text:='used+requested>300000';new_guard text:='used+requested>400000';old_count integer;new_count integer;
begin
 select pg_get_functiondef('gridiron_shared_private.write_operation(text,jsonb)'::regprocedure) into definition;
 old_count:=(length(definition)-length(replace(definition,old_guard,'')))/length(old_guard);
 new_count:=(length(definition)-length(replace(definition,new_guard,'')))/length(new_guard);
 if old_count=0 and new_count=1 then return;end if;
 if old_count<>1 or new_count<>0 or position('valid_public_capability(token)' in definition)=0 then raise exception 'Unexpected admission function; historical reservations were preserved';end if;
 execute replace(definition,old_guard,new_guard);
end $$;
