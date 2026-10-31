-- Preserve every prior whole-cent value while allowing exact sub-cent fee metadata.
-- Cash, stake, deposits, withdrawals and actual payouts remain whole cents.
alter table public.wagers alter column entry_fee_cents type numeric(26,6);

do $migration$
declare body text; before_value text; after_value text;
begin
 body:=pg_get_functiondef('gridiron_private.place_bet(jsonb)'::regprocedure);
 before_value:=$old$payload->>'entryFeeCents' !~ '^[0-9]{1,12}$'$old$;
 after_value:=$new$payload->>'entryFeeCents' !~ '^[0-9]{1,12}(\.[0-9]{1,6})?$'$new$;
 if position(before_value in body)=0 then raise exception 'Expected exact prior entry-fee validation before migration';end if;
 body:=replace(body,before_value,after_value);
 body:=replace(body,'Actual entry fee must be whole cents','Actual entry fee must be exact nonnegative cents with at most6decimal places');
 execute body;

 body:=pg_get_functiondef('gridiron_private.import_backup(jsonb,text)'::regprocedure);
 before_value:=$old$b->>'entry_fee_cents' !~ '^[0-9]{1,12}$'$old$;
 after_value:=$new$b->>'entry_fee_cents' !~ '^[0-9]{1,12}(\.[0-9]{1,6})?$'$new$;
 if position(before_value in body)=0 then raise exception 'Expected exact prior imported entry-fee validation before migration';end if;
 execute replace(body,before_value,after_value);

 body:=pg_get_functiondef('gridiron_private.ledger()'::regprocedure);
 if position('entry_fee_cents::text' in body)=0 then raise exception 'Expected prior ledger fee serialization before migration';end if;
 execute replace(body,'entry_fee_cents::text','trim_scale(entry_fee_cents)::text');
 body:=pg_get_functiondef('gridiron_private.export_financial()'::regprocedure);
 if position('b.entry_fee_cents::text' in body)=0 then raise exception 'Expected prior exported fee serialization before migration';end if;
 execute replace(body,'b.entry_fee_cents::text','trim_scale(b.entry_fee_cents)::text');
end $migration$;
