-- V6 exact player-outcome and bootstrap outputs require fresh full-game runs.
-- A 13-game slate uses 130,000 primary games; permit two such bounded passes
-- without discarding earlier simulations or decrementing any reserved counter.
-- This is application admission control, not a hosting-plan or billing change.
-- Provider hard quotas and the existing 300-second function deadline still apply.
do $$
declare definition text; old_guard text:='used+requested>150000';
 new_guard text:='used+requested>300000'; old_count integer; new_count integer;
begin
 select pg_get_functiondef('gridiron_shared_private.write_operation(text,jsonb)'::regprocedure) into definition;
 old_count:=(length(definition)-length(replace(definition,old_guard,'')))/length(old_guard);
 new_count:=(length(definition)-length(replace(definition,new_guard,'')))/length(new_guard);
 if old_count=0 and new_count=1 then return; end if;
 if old_count<>1 or new_count<>0 or position('valid_public_capability(token)' in definition)=0 then
  raise exception 'Unexpected public compute admission function; capacity was not changed';
 end if;
 -- CREATE OR REPLACE retains the original signature, privileges, capability
 -- authentication, transaction lock, lease fencing and accounting operations.
 execute replace(definition,old_guard,new_guard);
end $$;

-- Reversal, if an operator later chooses the smaller admission policy, must
-- guard and replace only this literal in the same function. Existing day/usage
-- rows, source snapshots and user financial data must never be reset.
