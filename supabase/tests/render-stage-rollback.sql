-- Managed staging database regression: controlled role/RPC tests, not HTTP login.
-- Entire synthetic test is rolled back. Never convert this into a migration.
begin;
insert into auth.users(id,email,role) values ('b7c4813b-dd16-4db9-976c-bcaeea6f1241','SYNTHETIC-render-stage-a@example.test','authenticated'),('b7c4813b-dd16-4db9-976c-bcaeea6f1242','SYNTHETIC-render-stage-b@example.test','authenticated');
select set_config('request.jwt.claims','{"sub":"b7c4813b-dd16-4db9-976c-bcaeea6f1241","role":"authenticated"}',true);
set local role authenticated;
select public.gridiron_post_transaction('{"sportsbook":"DraftKings","type":"starting_balance","amount":"100.00","reference":"SYNTHETIC-RENDER-STAGE-START"}'::jsonb);
select public.gridiron_post_transaction('{"sportsbook":"DraftKings","type":"deposit","amount":"50.00","reference":"SYNTHETIC-RENDER-STAGE-DEPOSIT"}'::jsonb);
select public.gridiron_post_transaction('{"sportsbook":"DraftKings","type":"withdrawal","amount":"20.00","reference":"SYNTHETIC-RENDER-STAGE-WITHDRAW"}'::jsonb);
select set_config('gridiron_stage.wager',(public.gridiron_place_bet('{"sportsbook":"DraftKings","event":"SYNTHETIC staging validation only","market":"Moneyline","selection":"SYNTHETIC selection","stake":"10.00","odds":-110}'::jsonb)->>'id'),true);
select public.gridiron_settle_bet(jsonb_build_object('id',current_setting('gridiron_stage.wager'),'result','won','payout','19.00'));
do $$declare v jsonb;begin v:=public.gridiron_ledger();if (v#>>'{summary,cashBalanceCents}')::int<>13900 or (v#>>'{summary,realizedPlCents}')::int<>900 or (v#>>'{summary,pendingExposureCents}')::int<>0 then raise exception 'Ledger invariant failed';end if;end$$;
select public.gridiron_save_workspace('{"id":"a1c594d6-f8cd-43d0-9b2d-75d78f01512c","mutationId":"28b7fc39-4bea-470a-b3c0-08fbd61cbe0b","expectedRevision":0,"kind":"combination","sport":"NFL","data":{"name":"SYNTHETIC Render stage validation","legs":[]}}'::jsonb);
select public.gridiron_save_workspace('{"id":"a1c594d6-f8cd-43d0-9b2d-75d78f01512c","mutationId":"18c90acf-6b2a-45a6-8188-f27b37e99f25","expectedRevision":1,"kind":"combination","sport":"NFL","data":{"name":"SYNTHETIC edited stage validation","legs":[]}}'::jsonb);
do $$begin if (select revision from public.research_workspaces where id='a1c594d6-f8cd-43d0-9b2d-75d78f01512c')<>2 then raise exception 'Research revision failed';end if;end$$;
reset role;
select set_config('request.jwt.claims','{"sub":"b7c4813b-dd16-4db9-976c-bcaeea6f1242","role":"authenticated"}',true);
set local role authenticated;
do $$begin if exists(select 1 from public.research_workspaces where id='a1c594d6-f8cd-43d0-9b2d-75d78f01512c') then raise exception 'Cross-user research leak';end if;if exists(select 1 from public.ledger_entries where user_id='b7c4813b-dd16-4db9-976c-bcaeea6f1241') then raise exception 'Cross-user ledger leak';end if;end$$;
rollback;
select not exists(select 1 from auth.users where id in('b7c4813b-dd16-4db9-976c-bcaeea6f1241','b7c4813b-dd16-4db9-976c-bcaeea6f1242')) as no_test_accounts_remain,not exists(select 1 from public.research_workspaces where id='a1c594d6-f8cd-43d0-9b2d-75d78f01512c') as no_test_research_remains;
