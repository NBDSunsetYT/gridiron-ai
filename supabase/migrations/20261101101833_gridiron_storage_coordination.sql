-- Additive operational metadata only. No existing table or row is moved/reset.
create table gridiron_shared_private.storage_outbox(
 id text primary key check(id ~ '^[a-f0-9]{64}$'),
 target text not null check(target='mongodb'),
 document_info jsonb not null check(octet_length(document_info::text)<=4096),
 stage jsonb not null check(octet_length(stage::text)<=1024),
 state text not null default 'pending' check(state in ('pending','processing','retry','delivered','dead_letter')),
 attempts integer not null default 0 check(attempts>=0),lease uuid,locked_at timestamptz,
 next_attempt_at timestamptz not null default now(),last_error_code text,
 created_at timestamptz not null default now(),updated_at timestamptz not null default now()
);
create index storage_outbox_due on gridiron_shared_private.storage_outbox(next_attempt_at,id) where state in ('pending','retry','processing');
create index storage_outbox_health on gridiron_shared_private.storage_outbox(state,updated_at);
create table gridiron_shared_private.storage_assets(
 id text primary key check(id ~ '^[a-f0-9]{64}$'),sport text not null check(sport in ('NFL','CFB')),
 kind text not null check(kind in ('datasets','artifacts','archives','temporary')),
 reference jsonb not null check(octet_length(reference::text)<=2048),
 bytes bigint not null check(bytes>=0),raw_bytes bigint not null check(raw_bytes>=0),
 protected boolean not null default true,backup_verified_at timestamptz,
 created_at timestamptz not null default now()
);
create table gridiron_shared_private.storage_integrity_alerts(
 document_id text not null check(document_id ~ '^[a-f0-9]{64}$'),
 code text not null check(code in ('external_document_mismatch','archive_checksum_mismatch')),
 first_seen_at timestamptz not null default now(),last_seen_at timestamptz not null default now(),
 occurrences bigint not null default 1,primary key(document_id,code)
);
alter table gridiron_shared_private.storage_outbox enable row level security;
alter table gridiron_shared_private.storage_assets enable row level security;
alter table gridiron_shared_private.storage_integrity_alerts enable row level security;
revoke all on gridiron_shared_private.storage_outbox,gridiron_shared_private.storage_assets,gridiron_shared_private.storage_integrity_alerts from public,anon,authenticated;

create function public.gridiron_storage_operation(token text,payload jsonb) returns jsonb
language plpgsql security definer set search_path='' as $$
declare action text:=payload->>'action';item gridiron_shared_private.storage_outbox;items jsonb;identity text:=payload->>'id';
begin
 if not gridiron_shared_private.valid_public_capability(token) then raise exception 'Storage service authorization required' using errcode='42501';end if;
 if action='enqueue' then
  if pg_database_size(current_database())>=470000000 or octet_length(payload::text)>8192 then raise exception 'Operational storage reserve protected' using errcode='54000';end if;
  if not coalesce(identity ~ '^[a-f0-9]{64}$'
   and jsonb_typeof(payload->'document')='object' and payload->'document'->>'_id'=identity
   and payload->'document'->>'schemaVersion'='1' and payload->'document'->>'sport' in ('NFL','CFB')
   and payload->'document'->>'kind' in ('simulation','injury_snapshot','matchup_report','explanation','source_metadata')
   and length(payload->'document'->>'gameId') between 1 and 120
   and payload->'document'->>'sha256' ~ '^[a-f0-9]{64}$'
   and payload->'stage'->'_sharedResearchObject'->>'version'='1'
   and payload->'stage'->'_sharedResearchObject'->>'id' ~ '^[a-f0-9]{64}$'
   and payload->'stage'->'_sharedResearchObject'->>'rawSha256'=payload->'document'->>'sha256'
   and (payload->'document'->>'bytes')::bigint between 0 and 2000000
   and (payload->'stage'->'_sharedResearchObject'->>'rawBytes')::bigint=(payload->'document'->>'bytes')::bigint,false)
   then raise exception 'Invalid delivery reference' using errcode='22023';end if;
  if not exists(select 1 from gridiron_shared_private.storage_outbox where id=identity) and (select count(*) from gridiron_shared_private.storage_outbox where state<>'delivered')>=1000 then raise exception 'Delivery queue admission protected' using errcode='54000';end if;
  insert into gridiron_shared_private.storage_outbox(id,target,document_info,stage) values(identity,'mongodb',payload->'document',payload->'stage') on conflict(id) do nothing;
  select * into item from gridiron_shared_private.storage_outbox where id=identity;
  if (item.document_info-'createdAt')<>((payload->'document')-'createdAt'::text) or item.stage<>payload->'stage' then raise exception 'Immutable delivery identity conflict' using errcode='23505';end if;
  return jsonb_build_object('id',item.id,'state',item.state);
 elsif action='claim' then
  update gridiron_shared_private.storage_outbox set state='dead_letter',lease=null,locked_at=null,last_error_code='worker_lease_exhausted',updated_at=now() where state='processing' and attempts>=8 and locked_at<now()-interval '5 minutes';
  with due as(select id from gridiron_shared_private.storage_outbox where (state in ('pending','retry') and next_attempt_at<=now()) or (state='processing' and locked_at<now()-interval '5 minutes') order by next_attempt_at,id limit greatest(1,least(coalesce((payload->>'limit')::integer,5),10)) for update skip locked),
  claimed as(update gridiron_shared_private.storage_outbox o set state='processing',lease=gen_random_uuid(),attempts=attempts+1,locked_at=now(),updated_at=now() from due where o.id=due.id returning o.*)
  select coalesce(jsonb_agg(to_jsonb(claimed)),'[]') into items from claimed;return items;
 elsif action in ('ack','fail') then
  select * into item from gridiron_shared_private.storage_outbox where id=identity for update;
  if item.id is null or item.state<>'processing' or item.lease is distinct from (payload->>'lease')::uuid then raise exception 'Delivery lease changed' using errcode='40001';end if;
  if action='ack' then
   if payload->>'sha256' is distinct from item.document_info->>'sha256' then raise exception 'Delivery checksum mismatch' using errcode='22023';end if;
   update gridiron_shared_private.storage_outbox set state='delivered',lease=null,locked_at=null,last_error_code=null,updated_at=now() where id=identity;
  else
   if coalesce(payload->>'code','') !~ '^[a-z_]{1,80}$' then raise exception 'Redacted error code required' using errcode='22023';end if;
   update gridiron_shared_private.storage_outbox set state=case when attempts>=8 then 'dead_letter' else 'retry' end,lease=null,locked_at=null,last_error_code=payload->>'code',next_attempt_at=now()+make_interval(secs=>least(3600,30*(2^least(attempts,7))::integer)),updated_at=now() where id=identity;
  end if;return jsonb_build_object('id',identity,'acknowledged',true);
 elsif action='archive_record' then
  if pg_database_size(current_database())>=470000000 or octet_length(payload::text)>4096 or identity !~ '^[a-f0-9]{64}$' or payload->'reference'->>'backend'<>'r2' or payload->'reference'->>'key' !~ '^(datasets|artifacts|archives|temporary)/(NFL|CFB)/[a-f0-9]{64}\.gz$' then raise exception 'Invalid bounded private archive reference' using errcode='22023';end if;
  insert into gridiron_shared_private.storage_assets(id,sport,kind,reference,bytes,raw_bytes,protected) values(identity,payload->>'sport',payload->>'kind',payload->'reference',(payload->'reference'->>'bytes')::bigint,(payload->'reference'->>'rawBytes')::bigint,true) on conflict(id) do nothing;
  if (select reference from gridiron_shared_private.storage_assets where id=identity)<>payload->'reference' then raise exception 'Immutable archive conflict' using errcode='23505';end if;
  return jsonb_build_object('id',identity,'recorded',true);
 elsif action='integrity_warning' then
  if identity !~ '^[a-f0-9]{64}$' or payload->>'code' not in ('external_document_mismatch','archive_checksum_mismatch') then raise exception 'Invalid redacted integrity alert' using errcode='22023';end if;
  insert into gridiron_shared_private.storage_integrity_alerts(document_id,code) values(identity,payload->>'code') on conflict(document_id,code) do update set last_seen_at=now(),occurrences=gridiron_shared_private.storage_integrity_alerts.occurrences+1;
  return jsonb_build_object('recorded',true);
 elsif action='health' then
  return jsonb_build_object('databaseBytes',pg_database_size(current_database()),'databaseLimitBytes',500000000,
   'sharedObjectBytes',(select coalesce(sum((metadata->>'size')::bigint),0) from storage.objects where bucket_id='gridiron-shared-research-v1' and metadata->>'size' ~ '^[0-9]+$'),
   'sharedObjectCount',(select count(*) from storage.objects where bucket_id='gridiron-shared-research-v1'),
   'outbox',(select coalesce(jsonb_object_agg(state,n),'{}') from(select state,count(*) n from gridiron_shared_private.storage_outbox group by state)s),
   'oldestPendingAt',(select min(created_at) from gridiron_shared_private.storage_outbox where state<>'delivered'),
   'r2CatalogBytes',(select coalesce(sum(bytes),0) from gridiron_shared_private.storage_assets),
   'simulationArchiveBytes',(select coalesce(sum(bytes),0) from gridiron_shared_private.storage_assets where kind='archives'),
   'verifiedBackupAssets',(select count(*) from gridiron_shared_private.storage_assets where backup_verified_at is not null),
   'integrityWarnings',(select coalesce(jsonb_agg(to_jsonb(a)),'[]') from(select document_id,code,first_seen_at,last_seen_at,occurrences from gridiron_shared_private.storage_integrity_alerts order by last_seen_at desc limit 20)a),
   'backupStatus','No automated backup/restore receipt has been verified by this storage coordinator.',
   'irreversibleCleanupEnabled',false);
 else raise exception 'Unsupported storage operation' using errcode='22023';end if;
end $$;
revoke all on function public.gridiron_storage_operation(text,jsonb) from public;
grant execute on function public.gridiron_storage_operation(text,jsonb) to anon,authenticated;
-- Rollback: disable v11 routing first, retain the outbox/assets for recovery.
-- This migration has no automatic deletion, TTL or private-account migration.
