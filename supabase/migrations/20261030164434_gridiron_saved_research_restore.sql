-- Preserve individual saved-research namespaces during verified v2 restoration.
-- No existing rows are rewritten; the original authenticated archive remains intact.
-- Only the namespace validation/INSERT target differs from the original import function.
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
  a:=gridiron_private.account_id(b->>'sportsbook');
  insert into public.wagers(id,user_id,account_id,event,market,selection,odds,stake_cents,placed_at,settled_at,result,payout_cents,notes,prediction,legs,created_at) values((b->>'id')::uuid,u,a,b->>'event',b->>'market',b->>'selection',(b->>'odds')::integer,(b->>'stake_cents')::numeric,(b->>'placed_at')::timestamptz,nullif(b->>'settled_at','')::timestamptz,b->>'result',nullif(b->>'payout_cents','')::numeric,coalesce(b->>'notes',''),case when jsonb_typeof(b->'prediction')='string' then (b->>'prediction')::jsonb else b->'prediction' end,case when jsonb_typeof(b->'legs')='string' then (b->>'legs')::jsonb else b->'legs' end,(b->>'created_at')::timestamptz);
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
