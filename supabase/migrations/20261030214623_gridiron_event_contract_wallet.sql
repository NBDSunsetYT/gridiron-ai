-- Preserve all existing wager/ledger rows. Event contracts retain actual prices,
-- never synthetic American odds. Existing ownership checks and RPC ACLs remain.
alter table public.wagers add column market_instrument text not null default 'sportsbook';
alter table public.wagers add column player text;
alter table public.wagers add column contract_price_cents numeric(20,6);
alter table public.wagers add column contract_quantity integer;
alter table public.wagers add column entry_fee_cents numeric(20,0);
alter table public.wagers alter column odds drop not null;
alter table public.wagers add constraint wagers_instrument_definition check(
 (market_instrument='sportsbook' and odds is not null and contract_price_cents is null and contract_quantity is null and entry_fee_cents is null)
 or (market_instrument='event_contract' and odds is null and contract_price_cents is not null and contract_price_cents>0 and contract_price_cents<=100
  and (contract_quantity is null or contract_quantity between 1 and 1000000)
  and (entry_fee_cents is null or entry_fee_cents between 0 and stake_cents)
  and (contract_quantity is null or (entry_fee_cents is not null and contract_price_cents*contract_quantity+entry_fee_cents=stake_cents)))
);
alter table public.wagers add constraint wagers_player_length check(player is null or length(player)<=180);

create or replace function gridiron_private.place_bet(payload jsonb) returns jsonb language plpgsql security definer set search_path='' as $$
declare u uuid:=gridiron_private.owner_id();a uuid;n numeric;odds_value integer;placed timestamptz:=coalesce(nullif(coalesce(payload->>'placementTime',payload->>'placedAt',payload->>'date'),'')::timestamptz,now());w uuid:=gen_random_uuid();j uuid;settings_value jsonb;tz text;lim numeric;spent numeric;leg jsonb;idx integer:=0;instrument text:=coalesce(payload->>'marketInstrument','sportsbook');player_value text:=nullif(trim(payload->>'player'),'');price_value numeric;quantity_value integer;fee_value numeric;begin
 perform pg_advisory_xact_lock(hashtextextended(u::text,0));a:=gridiron_private.account_id(payload->>'sportsbook');n:=gridiron_private.amount(payload->>'stake');
 if n<=0 or instrument not in ('sportsbook','event_contract') then raise exception 'Invalid stake or market instrument' using errcode='22023';end if;
 if length(coalesce(player_value,''))>180 or (payload?'player' and jsonb_typeof(payload->'player') not in ('string','null')) then raise exception 'Invalid recorded player' using errcode='22023';end if;
 if instrument='sportsbook' then
  odds_value:=(payload->>'odds')::integer;
  if abs(odds_value) not between 100 and 100000 or odds_value is null then raise exception 'Invalid American odds' using errcode='22023';end if;
  if nullif(payload->>'contractPriceCents','') is not null or nullif(payload->>'contractQuantity','') is not null or nullif(payload->>'entryFeeCents','') is not null then raise exception 'Contract price metadata requires an event-contract record' using errcode='22023';end if;
 else
  if nullif(payload->>'odds','') is not null then raise exception 'Event contracts do not have American odds' using errcode='22023';end if;
  if coalesce(payload->>'contractPriceCents','') !~ '^[0-9]{1,3}(\.[0-9]{1,6})?$' then raise exception 'Exact contract fill price required' using errcode='22023';end if;
  price_value:=(payload->>'contractPriceCents')::numeric;
  if price_value<=0 or price_value>100 then raise exception 'Contract price must be greater than zero and at most 100 cents' using errcode='22023';end if;
  if nullif(payload->>'entryFeeCents','') is not null then
   if payload->>'entryFeeCents' !~ '^[0-9]{1,12}$' then raise exception 'Actual entry fee must be whole cents' using errcode='22023';end if;
   fee_value:=(payload->>'entryFeeCents')::numeric;
   if fee_value>n then raise exception 'Entry fees exceed actual stake' using errcode='22023';end if;
  end if;
  if nullif(payload->>'contractQuantity','') is not null then
   if payload->>'contractQuantity' !~ '^[1-9][0-9]{0,6}$' then raise exception 'Contract quantity must be a whole number' using errcode='22023';end if;
   quantity_value:=(payload->>'contractQuantity')::integer;
   if quantity_value>1000000 or fee_value is null or price_value*quantity_value+fee_value<>n then raise exception 'Actual stake must equal contract fill price times quantity plus actual entry fees exactly' using errcode='22023';end if;
  end if;
 end if;
 if gridiron_private.balance(a)<n then raise exception 'Insufficient available balance' using errcode='22023';end if;
 if length(trim(coalesce(payload->>'event',''))) not between 1 and 300 or length(trim(coalesce(payload->>'market',''))) not between 1 and 200 or length(trim(coalesce(payload->>'selection',''))) not between 1 and 500 or placed>now()+interval '1 minute' then raise exception 'Event, market, selection and valid placement required' using errcode='22023';end if;
 select settings into settings_value from public.profiles where user_id=u;tz:=coalesce(settings_value->>'timezone','UTC');lim:=(settings_value->>'monthlyLimitCents')::numeric;
 if lim is not null then select coalesce(sum(stake_cents),0) into spent from public.wagers where user_id=u and date_trunc('month',placed_at at time zone tz)=date_trunc('month',placed at time zone tz);if spent+n>lim then raise exception 'Monthly stake limit exceeded' using errcode='22023';end if;end if;
 if payload?'legs' and payload->'legs'<>'null'::jsonb and (jsonb_typeof(payload->'legs')<>'array' or jsonb_array_length(payload->'legs') not between 2 and 12) then raise exception 'Parlays need 2-12 legs' using errcode='22023';end if;
 insert into public.wagers(id,user_id,account_id,event,market,selection,odds,stake_cents,placed_at,notes,prediction,legs,market_instrument,player,contract_price_cents,contract_quantity,entry_fee_cents) values(w,u,a,trim(payload->>'event'),trim(payload->>'market'),trim(payload->>'selection'),odds_value,n,placed,coalesce(payload->>'notes',payload->>'note',''),payload->'prediction',payload->'legs',instrument,player_value,price_value,quantity_value,fee_value);
 if jsonb_typeof(payload->'legs')='array' then for leg in select value from jsonb_array_elements(payload->'legs') loop idx:=idx+1;insert into public.wager_legs(user_id,wager_id,ordinal,selection,market,data) values(u,w,idx,coalesce(leg->>'selection','Recorded leg'),leg->>'market',leg);end loop;end if;
 j:=gridiron_private.write_entry(jsonb_build_object('account_id',a,'type','wager','amount',n,'date',placed,'note',payload->>'selection','related_id',w),jsonb_build_array(jsonb_build_object('account_id',a,'bucket','cash','amount',-n),jsonb_build_object('account_id',a,'bucket','escrow','amount',n)));
 return jsonb_build_object('id',w,'result','pending','stakeCents',n,'stake',(n/100)::numeric(20,2)::text,'marketInstrument',instrument,'player',player_value,'odds',odds_value,'contractPriceCents',price_value::text,'contractQuantity',quantity_value,'entryFeeCents',fee_value::text);
end$$;


create or replace function gridiron_private.settle_bet(payload jsonb) returns jsonb language plpgsql security definer set search_path='' as $$
declare u uuid:=gridiron_private.owner_id();b public.wagers%rowtype;result_value text:=payload->>'result';payout numeric;j uuid;at_time timestamptz:=coalesce(nullif(coalesce(payload->>'settlementTime',payload->>'settledAt',payload->>'date'),'')::timestamptz,now());begin
 perform pg_advisory_xact_lock(hashtextextended(u::text,0));select * into b from public.wagers where id=(payload->>'id')::uuid and user_id=u for update;
 if not found then raise exception 'Wager not found' using errcode='P0002';end if;if b.result<>'pending' then raise exception 'Wager already settled' using errcode='23505';end if;
 if result_value not in ('won','lost','voided','cashed_out') or result_value is null or at_time<b.placed_at or at_time>now()+interval '1 minute' then raise exception 'Invalid settlement result/time' using errcode='22023';end if;
 if result_value='lost' then payout:=0;if nullif(payload->>'payout','') is not null and gridiron_private.amount(payload->>'payout',true)<>0 then raise exception 'Lost wager payout must be zero' using errcode='22023';end if;
 elsif result_value='voided' then
  if b.market_instrument='event_contract' then
   if nullif(payload->>'payout','') is null then raise exception 'Actual contract refund including fee treatment is required' using errcode='22023';end if;
   payout:=gridiron_private.amount(payload->>'payout',true);
   if payout>b.stake_cents then raise exception 'Voided contract refund cannot exceed actual stake' using errcode='22023';end if;
  else payout:=b.stake_cents;if nullif(payload->>'payout','') is not null and gridiron_private.amount(payload->>'payout',true)<>payout then raise exception 'Void must return exactly the stake' using errcode='22023';end if;end if;
 elsif nullif(payload->>'payout','') is not null then payout:=gridiron_private.amount(payload->>'payout',true);
 elsif result_value='cashed_out' or b.market_instrument='event_contract' then raise exception 'Actual contract or cash-out payout required' using errcode='22023';
 else payout:=round(b.stake_cents*(1+case when b.odds>0 then b.odds::numeric/100 else 100::numeric/(-b.odds) end));end if;
 if payout<0 or payout>100000000000 or (result_value='won' and b.market_instrument='sportsbook' and payout<b.stake_cents) then raise exception 'Invalid total payout including returned stake' using errcode='22023';end if;
 update public.wagers set result=result_value,payout_cents=payout,settled_at=at_time where id=b.id and user_id=u;
 j:=gridiron_private.write_entry(jsonb_build_object('account_id',b.account_id,'type','settlement','amount',payout,'date',at_time,'note',result_value,'related_id',b.id),jsonb_build_array(jsonb_build_object('account_id',b.account_id,'bucket','escrow','amount',-b.stake_cents),jsonb_build_object('account_id',b.account_id,'bucket','cash','amount',payout),jsonb_build_object('account_id',b.account_id,'bucket','betting_pnl','amount',b.stake_cents-payout)));
 insert into public.settlements(user_id,wager_id,entry_id,result,payout_cents,settled_at) values(u,b.id,j,result_value,payout,at_time);
 return jsonb_build_object('id',b.id,'result',result_value,'payoutCents',payout,'payout',(payout/100)::numeric(20,2)::text,'profitCents',payout-b.stake_cents);
end$$;


create or replace function gridiron_private.ledger() returns jsonb language plpgsql security definer set search_path='' as $$
declare u uuid:=gridiron_private.owner_id();answer jsonb;begin perform gridiron_private.ensure_accounts();
with account_balances as (
 select a.id,a.sportsbook,coalesce(sum(p.amount_cents) filter(where p.bucket='cash'),0) cash,coalesce(sum(p.amount_cents) filter(where p.bucket='escrow'),0) escrow from public.sportsbook_accounts a left join public.ledger_postings p on p.account_id=a.id and p.user_id=u where a.user_id=u group by a.id,a.sportsbook
), journal_rows as (
 select e.*,a.sportsbook,exists(select 1 from public.ledger_entries r where r.user_id=u and r.reverses_id=e.id) reversed from public.ledger_entries e join public.sportsbook_accounts a on a.id=e.account_id and a.user_id=u where e.user_id=u
), bet_rows as (
 select b.*,a.sportsbook from public.wagers b join public.sportsbook_accounts a on a.id=b.account_id and a.user_id=u where b.user_id=u
), capital as (
 select coalesce(sum(amount_cents) filter(where type='deposit' and not reversed),0) deposits,coalesce(sum(amount_cents) filter(where type='withdrawal' and not reversed),0) withdrawals,coalesce(sum(amount_cents) filter(where type='starting_balance' and not reversed),0) starting from journal_rows
), totals as (
 select coalesce(sum(payout_cents-stake_cents) filter(where result<>'pending'),0) profit,coalesce(sum(stake_cents) filter(where result not in ('pending','voided')),0) settled_stake,count(*) total_bets,count(*) filter(where result<>'pending') settled_bets,coalesce(round(avg(stake_cents)),0) average_stake,greatest(0,coalesce(max(payout_cents-stake_cents) filter(where result<>'pending'),0)) largest_win,least(0,coalesce(min(payout_cents-stake_cents) filter(where result<>'pending'),0)) largest_loss from bet_rows
), daily as (
 select e.occurred_at::date AS bucket_date,sum(p.amount_cents) filter(where p.bucket in ('cash','escrow')) balance_change,-coalesce(sum(p.amount_cents) filter(where p.bucket='betting_pnl'),0) profit_change from public.ledger_entries e join public.ledger_postings p on p.entry_id=e.id and p.user_id=u where e.user_id=u group by e.occurred_at::date
), running as (select bucket_date,sum(coalesce(balance_change,0)) over(order by bucket_date) balance,sum(profit_change) over(order by bucket_date) profit from daily)
select jsonb_build_object(
 'accounts',(select coalesce(jsonb_agg(jsonb_build_object('sportsbook',sportsbook,'cashBalanceCents',cash+escrow,'availableBalanceCents',cash,'pendingExposureCents',escrow,'balance',((cash+escrow)/100)::numeric(20,2)::text) order by sportsbook),'[]'::jsonb) from account_balances),
 'transactions',(select coalesce(jsonb_agg(jsonb_build_object('id',id,'type',type,'sportsbook',sportsbook,'amountCents',amount_cents,'amount',(amount_cents/100)::numeric(20,2)::text,'date',occurred_at,'note',note,'reference',reference,'relatedId',related_id,'reversesId',reverses_id,'createdAt',created_at,'reversed',reversed) order by occurred_at desc,created_at desc),'[]'::jsonb) from journal_rows),
 'bets',(select coalesce(jsonb_agg(jsonb_build_object('id',id,'sportsbook',sportsbook,'event',event,'market',market,'selection',selection,'odds',odds,'marketInstrument',market_instrument,'player',player,'contractPriceCents',contract_price_cents::text,'contractQuantity',contract_quantity,'entryFeeCents',entry_fee_cents::text,'stakeCents',stake_cents,'stake',(stake_cents/100)::numeric(20,2)::text,'placedAt',placed_at,'settledAt',settled_at,'result',result,'payoutCents',payout_cents,'payout',(payout_cents/100)::numeric(20,2)::text,'notes',notes,'prediction',prediction,'legs',legs) order by placed_at desc),'[]'::jsonb) from bet_rows),
 'summary',(select jsonb_build_object('cashBalanceCents',(select coalesce(sum(cash+escrow),0) from account_balances),'availableBalanceCents',(select coalesce(sum(cash),0) from account_balances),'pendingExposureCents',(select coalesce(sum(escrow),0) from account_balances),'realizedPlCents',t.profit,'totalDepositsCents',c.deposits,'totalWithdrawalsCents',c.withdrawals,'netCashContributedCents',c.starting+c.deposits-c.withdrawals,'settledStakeCents',t.settled_stake,'roi',t.profit/nullif(t.settled_stake,0),'averageStakeCents',t.average_stake,'largestWinCents',t.largest_win,'largestLossCents',t.largest_loss,'totalBets',t.total_bets,'settledBets',t.settled_bets) from capital c cross join totals t),
 'chart',(select coalesce(jsonb_agg(jsonb_build_object('date',bucket_date,'balanceCents',balance,'profitCents',profit) order by bucket_date),'[]'::jsonb) from running),
 'audit',(select coalesce(jsonb_agg(jsonb_build_object('action',action,'entityId',entity_id,'detail',detail,'createdAt',created_at) order by created_at desc),'[]'::jsonb) from (select * from public.audit_log where user_id=u order by created_at desc limit 200) x),
 'performanceByMarket',(select coalesce(jsonb_agg(x),'[]'::jsonb) from (select market,count(*) bets,sum(stake_cents) "stakeCents",sum(payout_cents-stake_cents) "profitCents",sum(payout_cents-stake_cents)/nullif(sum(stake_cents),0) roi from bet_rows where result not in ('pending','voided') group by market) x),
 'performanceBySportsbook',(select coalesce(jsonb_agg(x),'[]'::jsonb) from (select a.sportsbook,count(b.id) bets,coalesce(sum(b.stake_cents),0) "stakeCents",coalesce(sum(b.payout_cents-b.stake_cents),0) "profitCents",sum(b.payout_cents-b.stake_cents)/nullif(sum(b.stake_cents),0) roi from account_balances a left join bet_rows b on b.account_id=a.id and b.result not in ('pending','voided') group by a.sportsbook) x)
) into answer;return answer;end$$;


create or replace function gridiron_private.export_financial() returns jsonb language plpgsql security definer set search_path='' as $$declare u uuid:=gridiron_private.owner_id();answer jsonb;begin
select jsonb_build_object(
 'journal',(select coalesce(jsonb_agg(jsonb_build_object('id',e.id,'user_id',e.user_id,'type',e.type,'sportsbook',a.sportsbook,'amount_cents',e.amount_cents,'date',e.occurred_at,'note',e.note,'reference',e.reference,'related_id',e.related_id,'reverses_id',e.reverses_id,'created_at',e.created_at) order by e.occurred_at,e.created_at),'[]'::jsonb) from public.ledger_entries e join public.sportsbook_accounts a on a.id=e.account_id and a.user_id=u where e.user_id=u),
 'postings',(select coalesce(jsonb_agg(jsonb_build_object('id',p.id,'journal_id',p.entry_id,'account',p.bucket,'sportsbook',a.sportsbook,'amount_cents',p.amount_cents)),'[]'::jsonb) from public.ledger_postings p join public.sportsbook_accounts a on a.id=p.account_id and a.user_id=u where p.user_id=u),
 'bets',(select coalesce(jsonb_agg(jsonb_build_object('id',b.id,'user_id',b.user_id,'sportsbook',a.sportsbook,'event',b.event,'market',b.market,'selection',b.selection,'odds',b.odds,'market_instrument',b.market_instrument,'player',b.player,'contract_price_cents',b.contract_price_cents::text,'contract_quantity',b.contract_quantity,'entry_fee_cents',b.entry_fee_cents::text,'stake_cents',b.stake_cents,'placed_at',b.placed_at,'settled_at',b.settled_at,'result',b.result,'payout_cents',b.payout_cents,'notes',b.notes,'prediction',b.prediction,'legs',b.legs,'created_at',b.created_at) order by b.placed_at),'[]'::jsonb) from public.wagers b join public.sportsbook_accounts a on a.id=b.account_id and a.user_id=u where b.user_id=u),
 'audit',(select coalesce(jsonb_agg(jsonb_build_object('id',a.id,'user_id',a.user_id,'action',a.action,'entity_id',a.entity_id,'detail',a.detail,'created_at',a.created_at) order by a.created_at),'[]'::jsonb) from public.audit_log a where a.user_id=u)
) into answer;return answer;end$$;


create or replace function gridiron_private.import_backup(payload jsonb,import_hash text) returns jsonb language plpgsql security definer set search_path='' as $$
declare
 u uuid:=gridiron_private.owner_id();j jsonb;p jsonb;b jsonb;r jsonb;v jsonb;table_name text;kv record;a uuid;source_id uuid;entry_count integer:=0;bet_count integer:=0;record_count integer:=0;id_value uuid;reference_value text;source_user text;actual numeric;expected numeric;parsed jsonb;conv jsonb;msg jsonb;
begin
 perform pg_advisory_xact_lock(hashtextextended(u::text,0));
 if import_hash is null or import_hash!~'^[a-f0-9]{64}$' then raise exception 'A verified SHA-256 import hash is required' using errcode='22023';end if;
 if exists(select 1 from public.data_imports where user_id=u and source_hash=import_hash and kind='legacy_backup') then return jsonb_build_object('imported',false,'duplicate',true,'message','This exact backup was already imported');end if;
 if exists(select 1 from public.ledger_entries where user_id=u) or exists(select 1 from public.wagers where user_id=u) then raise exception 'Import requires an empty cloud financial workspace; existing cloud records were preserved' using errcode='22023';end if;
 if (payload->>'version')::integer<>2 or jsonb_typeof(payload->'rawLedger'->'journal')<>'array' or jsonb_typeof(payload->'rawLedger'->'postings')<>'array' or jsonb_typeof(payload->'rawLedger'->'bets')<>'array' then raise exception 'A complete version 2 raw-ledger backup is required' using errcode='22023';end if;
 if jsonb_array_length(payload->'rawLedger'->'journal')>100000 or jsonb_array_length(payload->'rawLedger'->'postings')>300000 then raise exception 'Backup exceeds interactive migration bounds' using errcode='22023';end if;
 -- Validate every source journal before writing anything. No orphan or unbalanced posting is accepted.
 if exists(select 1 from jsonb_array_elements(payload->'rawLedger'->'postings') lp where not exists(select 1 from jsonb_array_elements(payload->'rawLedger'->'journal') le where le->>'id'=lp->>'journal_id')) then raise exception 'Backup has orphan postings' using errcode='22023';end if;
 for j in select value from jsonb_array_elements(payload->'rawLedger'->'journal') loop
  source_id:=(j->>'id')::uuid;
  if (j->>'amount_cents')::numeric<>trunc((j->>'amount_cents')::numeric) or j->>'sportsbook' not in ('DraftKings','Hard Rock') then raise exception 'Invalid exact source journal' using errcode='22023';end if;
  select coalesce(sum((lp->>'amount_cents')::numeric),0) into actual from jsonb_array_elements(payload->'rawLedger'->'postings') lp where lp->>'journal_id'=j->>'id';
  if actual<>0 or (select count(*) from jsonb_array_elements(payload->'rawLedger'->'postings') lp where lp->>'journal_id'=j->>'id')<2 then raise exception 'Backup journal is not balanced' using errcode='22023';end if;
 end loop;
 perform gridiron_private.ensure_accounts();
 for j in select value from jsonb_array_elements(payload->'rawLedger'->'journal') loop
  a:=gridiron_private.account_id(j->>'sportsbook');
  insert into public.ledger_entries(id,user_id,account_id,type,amount_cents,occurred_at,note,reference,related_id,reverses_id,created_at) values((j->>'id')::uuid,u,a,j->>'type',(j->>'amount_cents')::numeric,(j->>'date')::timestamptz,coalesce(j->>'note',''),nullif(j->>'reference',''),nullif(j->>'related_id','')::uuid,nullif(j->>'reverses_id','')::uuid,(j->>'created_at')::timestamptz);
  entry_count:=entry_count+1;
 end loop;
 for p in select value from jsonb_array_elements(payload->'rawLedger'->'postings') loop
  if (p->>'amount_cents')::numeric<>trunc((p->>'amount_cents')::numeric) then raise exception 'Fractional-cent posting rejected' using errcode='22023';end if;
  a:=gridiron_private.account_id(p->>'sportsbook');
  insert into public.ledger_postings(user_id,entry_id,account_id,bucket,amount_cents) values(u,(p->>'journal_id')::uuid,a,p->>'account',(p->>'amount_cents')::numeric);
 end loop;
 for b in select value from jsonb_array_elements(payload->'rawLedger'->'bets') loop
  if coalesce(b->>'market_instrument','sportsbook')='event_contract' and
   (coalesce(b->>'contract_price_cents','') !~ '^[0-9]{1,3}(\.[0-9]{1,6})?$'
    or (nullif(b->>'contract_quantity','') is not null and b->>'contract_quantity' !~ '^[1-9][0-9]{0,6}$')
    or (nullif(b->>'entry_fee_cents','') is not null and b->>'entry_fee_cents' !~ '^[0-9]{1,12}$')) then
   raise exception 'Invalid exact event-contract backup fields' using errcode='22023';
  end if;
  a:=gridiron_private.account_id(b->>'sportsbook');
  insert into public.wagers(id,user_id,account_id,event,market,selection,odds,stake_cents,placed_at,settled_at,result,payout_cents,notes,prediction,legs,created_at,market_instrument,player,contract_price_cents,contract_quantity,entry_fee_cents) values((b->>'id')::uuid,u,a,b->>'event',b->>'market',b->>'selection',(b->>'odds')::integer,(b->>'stake_cents')::numeric,(b->>'placed_at')::timestamptz,nullif(b->>'settled_at','')::timestamptz,b->>'result',nullif(b->>'payout_cents','')::numeric,coalesce(b->>'notes',''),case when jsonb_typeof(b->'prediction')='string' then (b->>'prediction')::jsonb else b->'prediction' end,case when jsonb_typeof(b->'legs')='string' then (b->>'legs')::jsonb else b->'legs' end,(b->>'created_at')::timestamptz,coalesce(b->>'market_instrument','sportsbook'),nullif(b->>'player',''),nullif(b->>'contract_price_cents','')::numeric,nullif(b->>'contract_quantity','')::integer,nullif(b->>'entry_fee_cents','')::numeric);
  bet_count:=bet_count+1;
 end loop;
 -- Reconstruct relational settlements from immutable imported ledger references.
 insert into public.settlements(user_id,wager_id,entry_id,result,payout_cents,settled_at)
 select u,w.id,e.id,w.result,w.payout_cents,w.settled_at from public.wagers w join public.ledger_entries e on e.user_id=u and e.related_id=w.id and e.type='settlement' where w.user_id=u and w.result<>'pending';
 for r in select value from jsonb_array_elements(coalesce(payload->'rawLedger'->'audit','[]'::jsonb)) loop
  insert into public.audit_log(user_id,action,entity_id,detail,created_at) values(u,r->>'action',nullif(r->>'entity_id','')::uuid,case when jsonb_typeof(r->'detail')='string' then (r->>'detail')::jsonb else coalesce(r->'detail','{}'::jsonb) end,coalesce(nullif(r->>'created_at','')::timestamptz,now()));
 end loop;
 -- A post-import report must reconcile exactly with the pre-upgrade source export.
 select coalesce(sum(amount_cents) filter(where bucket in ('cash','escrow')),0) into actual from public.ledger_postings where user_id=u;
 expected:=(payload->'ledger'->'summary'->>'cashBalanceCents')::numeric;
 if expected is null or actual<>expected then raise exception 'Imported bankroll does not reconcile with source report; no records committed' using errcode='22023';end if;
 select coalesce(sum(payout_cents-stake_cents) filter(where result<>'pending'),0) into actual from public.wagers where user_id=u;
 expected:=(payload->'ledger'->'summary'->>'realizedPlCents')::numeric;
 if expected is null or actual<>expected then raise exception 'Imported realized P/L does not reconcile; no records committed' using errcode='22023';end if;
 if jsonb_typeof(payload->'settings')='object' then perform gridiron_private.update_settings(payload->'settings');end if;
 if jsonb_typeof(payload->'preferences')='object' then for kv in select * from jsonb_each(payload->'preferences') loop insert into public.preferences(user_id,key,value) values(u,kv.key,kv.value) on conflict(user_id,key) do update set value=excluded.value,updated_at=now();end loop;end if;
 -- Preserve the entire original, authenticated/decrypted export in the owner's cloud archive too.
 insert into public.gridiron_records(user_id,kind,entity_key,data,source,version) values(u,'legacy_backup_archive',import_hash,payload,'verified account backup','2');
 for kv in select * from jsonb_each(coalesce(payload->'research','{}'::jsonb)) loop
  table_name:=kv.key;if jsonb_typeof(kv.value)<>'array' or table_name in ('conversations','conversation_messages') then continue;end if;
  for r in select value from jsonb_array_elements(kv.value) loop
   if table_name='research_records' and ((r->>'kind') is null or (r->>'kind')!~'^[a-z][a-z0-9_-]{0,49}$') then raise exception 'Invalid saved research kind; original archive was not changed' using errcode='22023';end if;
   id_value:=coalesce(nullif(r->>'id','')::uuid,gen_random_uuid());
   parsed:=case when jsonb_typeof(r->'data')='string' then (r->>'data')::jsonb when r?'data' then r->'data' else r end;
   if table_name='simulation_jobs' then parsed:=jsonb_build_object('id',id_value,'kind',r->>'kind','status',r->>'status','data',parsed,'result',case when jsonb_typeof(r->'result')='string' then (r->>'result')::jsonb else r->'result' end,'error',r->>'error','createdAt',r->>'created_at','updatedAt',r->>'updated_at');
   elsif table_name='simulation_inputs' then parsed:=jsonb_build_object('jobId',r->>'job_id','input',parsed);
   else parsed:=parsed||jsonb_build_object('id',id_value,'createdAt',coalesce(r->>'created_at',now()::text));end if;
   insert into public.gridiron_records(id,user_id,kind,entity_key,data,source,observed_at,created_at,updated_at) values(id_value,u,case when table_name='research_records' then 'research_records/'||(r->>'kind') else table_name end,coalesce(r->>'entity_key',r->>'contract_id',r->>'job_id',''),parsed,coalesce(r->>'source','verified account backup'),coalesce(nullif(r->>'observed_at','')::timestamptz,nullif(r->>'quoted_at','')::timestamptz,nullif(r->>'created_at','')::timestamptz,now()),coalesce(nullif(r->>'created_at','')::timestamptz,now()),coalesce(nullif(r->>'updated_at','')::timestamptz,nullif(r->>'created_at','')::timestamptz,now()));record_count:=record_count+1;
  end loop;
 end loop;
 for conv in select value from jsonb_array_elements(coalesce(payload->'research'->'conversations','[]'::jsonb)) loop
  insert into public.conversations(id,user_id,title,created_at,updated_at) values((conv->>'id')::uuid,u,conv->>'title',(conv->>'created_at')::timestamptz,(conv->>'updated_at')::timestamptz);
 end loop;
 for msg in select value from jsonb_array_elements(coalesce(payload->'research'->'conversation_messages','[]'::jsonb)) loop
  insert into public.conversation_messages(id,user_id,conversation_id,role,content,data,created_at) values((msg->>'id')::uuid,u,(msg->>'conversation_id')::uuid,msg->>'role',msg->>'content',case when jsonb_typeof(msg->'data')='string' then (msg->>'data')::jsonb else coalesce(msg->'data','{}'::jsonb) end,(msg->>'created_at')::timestamptz);
 end loop;
 insert into public.data_imports(user_id,source_hash,kind,row_count) values(u,import_hash,'legacy_backup',entry_count+bet_count+record_count);
 insert into public.audit_log(user_id,action,detail) values(u,'legacy_backup_import',jsonb_build_object('hash',import_hash,'journalEntries',entry_count,'wagers',bet_count,'researchRecords',record_count));
 return jsonb_build_object('imported',true,'duplicate',false,'journalEntries',entry_count,'wagers',bet_count,'researchRecords',record_count,'sourcePreserved',true);
end$$;

