-- A bounded application admission pool; no provider plan or payment changes.
-- Preserve every existing reservation. The v6 overnight total is retained;
-- the v7 full-game release validation and explicit private research share this
-- same pool. Public storage still independently stops before private headroom.
do $$
declare definition text;name text;old_guard text:='used+requested>400000';new_guard text:='used+requested>500000';old_count integer;new_count integer;changed integer:=0;
begin
 foreach name in array array['gridiron_shared_private.write_operation(text,jsonb)','gridiron_shared_private.write_operation_v1(text,jsonb)'] loop
  select pg_get_functiondef(to_regprocedure(name)) into definition;
  if definition is null then continue;end if;
  old_count:=(length(definition)-length(replace(definition,old_guard,'')))/length(old_guard);
  new_count:=(length(definition)-length(replace(definition,new_guard,'')))/length(new_guard);
  if old_count=0 and new_count=0 then continue;end if;
  if old_count=0 and new_count=1 then changed:=changed+1;continue;end if;
  if old_count<>1 or new_count<>0 or position('valid_public_capability(token)' in definition)=0 then raise exception 'Unexpected admission function; historical reservations were preserved';end if;
  execute replace(definition,old_guard,new_guard);changed:=changed+1;
 end loop;
 if changed<>1 then raise exception 'Exactly one verified admission guard is required';end if;
end $$;
