-- SYNTHETIC temporary users only. Everything below rolls back.
-- Run with the authorized project administration SQL tool, never as app SQL.
begin;
insert into auth.users(id,email) values
 ('ee000000-0000-4000-8000-000000000001','gridiron-rls-1@example.invalid'),
 ('ee000000-0000-4000-8000-000000000002','gridiron-rls-2@example.invalid');
set local role authenticated;
select set_config('request.jwt.claims','{"sub":"ee000000-0000-4000-8000-000000000001","role":"authenticated"}',true);
select public.gridiron_post_transaction('{"type":"deposit","amount":"1000.00","sportsbook":"DraftKings"}');
select public.gridiron_post_transaction('{"type":"withdrawal","amount":"150.00","sportsbook":"DraftKings"}');
do $$declare bet jsonb;report jsonb;begin
 bet:=public.gridiron_place_bet('{"sportsbook":"DraftKings","event":"SYNTHETIC RLS GAME","market":"moneyline","selection":"SYNTHETIC","odds":-110,"stake":"100.00"}');
 report:=public.gridiron_ledger();
 if (report->'summary'->>'availableBalanceCents')::numeric<>75000 then raise exception 'Pending available balance mismatch';end if;
 perform public.gridiron_settle_bet(jsonb_build_object('id',bet->>'id','result','won','payout','175.00'));
 perform public.gridiron_post_transaction('{"type":"transfer","amount":"50.00","sportsbook":"DraftKings","toSportsbook":"Hard Rock"}');
 report:=public.gridiron_ledger();
 if (report->'summary'->>'cashBalanceCents')::numeric<>92500 or (report->'summary'->>'realizedPlCents')::numeric<>7500 then raise exception 'Settled balance or realized P/L mismatch';end if;
 begin perform public.gridiron_settle_bet(jsonb_build_object('id',bet->>'id','result','won','payout','175.00'));raise exception 'Repeated settlement was accepted';exception when unique_violation then null;end;
end$$;
insert into public.conversations(id,user_id,title) values('ee100000-0000-4000-8000-000000000001','ee000000-0000-4000-8000-000000000001','SYNTHETIC private research');
select set_config('request.jwt.claims','{"sub":"ee000000-0000-4000-8000-000000000002","role":"authenticated"}',true);
do $$declare n integer;report jsonb;begin
 select count(*) into n from public.ledger_entries;if n<>0 then raise exception 'Cross-user ledger read allowed';end if;
 select count(*) into n from public.conversations where id='ee100000-0000-4000-8000-000000000001';if n<>0 then raise exception 'Cross-user conversation read allowed';end if;
 report:=public.gridiron_ledger();if (report->'summary'->>'cashBalanceCents')::numeric<>0 then raise exception 'Second account received first account balance';end if;
 begin insert into public.ledger_postings(user_id,entry_id,account_id,bucket,amount_cents) values('ee000000-0000-4000-8000-000000000002','ee000000-0000-4000-8000-000000000001','ee000000-0000-4000-8000-000000000001','cash',100);raise exception 'Direct forged posting accepted';exception when insufficient_privilege then null;end;
 begin insert into public.conversations(user_id,title) values('ee000000-0000-4000-8000-000000000001','SYNTHETIC forbidden');raise exception 'Cross-owner INSERT accepted';exception when insufficient_privilege then null;end;
end$$;
select jsonb_build_object('status','passed','checks',array['exact ledger arithmetic','withdrawals excluded from P/L','transfer neutral','duplicate settlement rejected','RLS owner isolation','direct posting rejected','conversation ownership'],'syntheticFixture',true,'rollback',true) as verification;
rollback;
