-- Exact manual contract identity remains stable across snapshots and concurrent imports.
create index gridiron_quote_identity_lookup on public.gridiron_records(user_id,(data->>'contractId')) where kind='contract_quotes';
create function gridiron_private.check_contract_identity() returns trigger language plpgsql security invoker set search_path='' as $$
declare cid text;prior jsonb;field text;begin
 if new.kind<>'contract_quotes' then return new;end if;
 if auth.uid() is null or auth.uid()<>new.user_id then raise exception 'Quote owner must be the authenticated account' using errcode='42501';end if;
 cid:=new.data->>'contractId';
 if cid is null or length(cid) not between 1 and 180 then raise exception 'Exact contract ID required' using errcode='22023';end if;
 perform pg_advisory_xact_lock(hashtextextended(new.user_id::text||':contract:'||cid,0));
 for prior in select data from public.gridiron_records where user_id=new.user_id and kind='contract_quotes' and data->>'contractId'=cid loop
  foreach field in array array['eventId','threshold','operator','eventStart','settlementRule'] loop
   if prior->field is distinct from new.data->field then raise exception 'Contract identity/rules cannot change for the same contract ID' using errcode='22023';end if;
  end loop;
  if prior?'settlementDefinition' and prior->'settlementDefinition'<>'null'::jsonb and prior->'settlementDefinition' is distinct from new.data->'settlementDefinition' then raise exception 'Established structured settlement rules cannot change' using errcode='22023';end if;
 end loop;
 new.entity_key:=cid;return new;
end$$;
create trigger gridiron_quote_identity before insert on public.gridiron_records for each row execute function gridiron_private.check_contract_identity();
revoke all on function gridiron_private.check_contract_identity() from public,anon,authenticated;
