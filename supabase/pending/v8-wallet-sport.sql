-- Pending additive patch. The database/security owner applies this only as part
-- of a versioned migration after a verified recovery checkpoint. No row updates,
-- financial formulas, RLS policies, grants or prediction snapshots are changed.
-- A rollback must retain this nullable column and its recorded metadata; restore
-- prior function definitions from the checkpoint rather than dropping user data.
alter table public.wagers add column sport text check(sport in ('NFL','CFB'));

do $migration$
declare body text; before_value text; after_value text;
begin
 body:=pg_get_functiondef('gridiron_private.place_bet(jsonb)'::regprocedure);
 before_value:=' perform pg_advisory_xact_lock(hashtextextended(u::text,0));';
 after_value:=$sport$ if payload?'sport' and (jsonb_typeof(payload->'sport') is distinct from 'string' or payload->>'sport' not in ('NFL','CFB')) then raise exception 'Wager sport must be NFL or CFB when supplied' using errcode='22023';end if;
 perform pg_advisory_xact_lock(hashtextextended(u::text,0));$sport$;
 if position(before_value in body)=0 then raise exception 'Expected prior place-bet ownership lock before sport migration';end if;
 body:=replace(body,before_value,after_value);
 before_value:='contract_quantity,entry_fee_cents) values';after_value:='contract_quantity,entry_fee_cents,sport) values';
 if position(before_value in body)=0 then raise exception 'Expected prior place-bet columns before sport migration';end if;
 body:=replace(body,before_value,after_value);
 before_value:='quantity_value,fee_value);';after_value:=$sport$quantity_value,fee_value,payload->>'sport');$sport$;
 if position(before_value in body)=0 then raise exception 'Expected prior place-bet values before sport migration';end if;
 body:=replace(body,before_value,after_value);
 before_value:=$old$'marketInstrument',instrument,$old$;after_value:=$new$'sport',payload->>'sport','marketInstrument',instrument,$new$;
 if position(before_value in body)=0 then raise exception 'Expected prior place-bet response before sport migration';end if;
 execute replace(body,before_value,after_value);

 body:=pg_get_functiondef('gridiron_private.ledger()'::regprocedure);
 before_value:=$old$'sportsbook',sportsbook,'event',event,$old$;after_value:=$new$'sportsbook',sportsbook,'sport',sport,'event',event,$new$;
 if position(before_value in body)=0 then raise exception 'Expected prior ledger projection before sport migration';end if;
 execute replace(body,before_value,after_value);

 body:=pg_get_functiondef('gridiron_private.export_financial()'::regprocedure);
 before_value:=$old$'sportsbook',a.sportsbook,'event',b.event,$old$;after_value:=$new$'sportsbook',a.sportsbook,'sport',b.sport,'event',b.event,$new$;
 if position(before_value in body)=0 then raise exception 'Expected prior export projection before sport migration';end if;
 execute replace(body,before_value,after_value);

 body:=pg_get_functiondef('gridiron_private.import_backup(jsonb,text)'::regprocedure);
 before_value:=$old$  a:=gridiron_private.account_id(b->>'sportsbook');$old$;
 after_value:=$new$  if b?'sport' and b->'sport'<>'null'::jsonb and (jsonb_typeof(b->'sport') is distinct from 'string' or b->>'sport' not in ('NFL','CFB')) then raise exception 'Invalid recorded wager sport in backup' using errcode='22023';end if;
  a:=gridiron_private.account_id(b->>'sportsbook');$new$;
 if position(before_value in body)=0 then raise exception 'Expected prior backup wager ownership lookup before sport migration';end if;
 body:=replace(body,before_value,after_value);
 before_value:='contract_quantity,entry_fee_cents) values';after_value:='contract_quantity,entry_fee_cents,sport) values';
 if position(before_value in body)=0 then raise exception 'Expected prior imported wager columns before sport migration';end if;
 body:=replace(body,before_value,after_value);
 before_value:=$old$nullif(b->>'entry_fee_cents','')::numeric);$old$;after_value:=$new$nullif(b->>'entry_fee_cents','')::numeric,b->>'sport');$new$;
 if position(before_value in body)=0 then raise exception 'Expected prior imported wager values before sport migration';end if;
 execute replace(body,before_value,after_value);
end $migration$;
