-- Additive compact public-football references only. No private table changes.
-- Payloads live in the existing private, checksummed compressed object store.
create table public.football_learning_records(
 id text primary key check(id ~ '^[a-f0-9]{64}$'),
 kind text not null check(kind in ('forecast','actual','evaluation','journal','candidate','promotion','rollback')),
 sport text not null check(sport in ('NFL','CFB')),
 game_id text not null check(length(game_id) between 1 and 120),
 event_start timestamptz not null,
 model_version text not null check(length(model_version) between 1 and 160),
 parent_id text references public.football_learning_records(id),
 mode text not null check(mode in ('pregame','retrospective','observed')),
 pointer jsonb not null check(jsonb_typeof(pointer)='object' and octet_length(pointer::text)<1800),
 summary jsonb not null check(jsonb_typeof(summary)='object' and octet_length(summary::text)<3500),
 created_at timestamptz not null default clock_timestamp()
);
create index football_learning_kind_sport_time on public.football_learning_records(kind,sport,event_start desc,id);
create index football_learning_parent on public.football_learning_records(parent_id,created_at desc);
create index football_learning_game on public.football_learning_records(sport,game_id,kind,created_at desc);
alter table public.football_learning_records enable row level security;
revoke all on public.football_learning_records from anon,authenticated;
grant select on public.football_learning_records to anon,authenticated;
create policy public_football_learning_read on public.football_learning_records for select to anon,authenticated using(true);
create function gridiron_shared_private.learning_immutable() returns trigger language plpgsql set search_path=pg_catalog as $$begin raise exception 'Learning history is append-only' using errcode='42501';end$$;
create trigger football_learning_immutable before update or delete on public.football_learning_records for each row execute function gridiron_shared_private.learning_immutable();

create function gridiron_shared_private.learning_write(token text,payload jsonb) returns jsonb
language plpgsql security definer set search_path=pg_catalog as $$
declare r public.football_learning_records; p public.football_learning_records; m text; legacy public.shared_nfl_snapshots; archived timestamptz; at_time timestamptz:=(payload->>'eventStart')::timestamptz;
begin
 if not gridiron_shared_private.valid_public_capability(token) then raise exception 'Server capability required' using errcode='42501';end if;
 if jsonb_typeof(payload) is distinct from 'object' or octet_length(payload::text)>6500 or payload->>'id' is null then raise exception 'Compact public learning reference required' using errcode='22023';end if;
 select * into r from public.football_learning_records where id=payload->>'id';
 if found then
  if r.sport is distinct from payload->>'sport' or r.game_id is distinct from payload->>'gameId' or r.kind is distinct from payload->>'kind' then raise exception 'Learning identity conflict' using errcode='23505';end if;
  return to_jsonb(r);
 end if;
 if pg_database_size(current_database())>=480000000 then raise exception 'Research metadata reserve reached; existing history preserved' using errcode='54000';end if;
 if payload->>'kind'='forecast' then
  archived:=clock_timestamp();
  -- A legacy archive date is trusted only after matching the immutable original
  -- snapshot on the server. JSON timestamps alone can never backdate a forecast.
  if payload->>'legacySnapshotId' is not null then
   select * into legacy from public.shared_nfl_snapshots where id=(payload->>'legacySnapshotId')::uuid;
   if not found or legacy.game_id is distinct from payload->>'gameId' or legacy.input_hash is distinct from payload->'summary'->>'inputVersion' then raise exception 'Original snapshot identity unavailable' using errcode='22023';end if;
   archived:=legacy.created_at;
  end if;
  m:=case when archived<at_time and (payload->'summary'->>'predictedAt')::timestamptz<=archived and coalesce((payload->>'retrospective')::boolean,false)=false then 'pregame' else 'retrospective' end;
 elsif payload->>'kind'='evaluation' then
  select * into p from public.football_learning_records where id=payload->>'parentId' and kind='forecast';
  if not found or p.sport is distinct from payload->>'sport' or p.game_id is distinct from payload->>'gameId' or p.event_start is distinct from at_time then raise exception 'Matching frozen forecast required' using errcode='22023';end if;
  m:=p.mode;
 else m:='observed';end if;
 if payload->'pointer'->'_sharedResearchObject'->>'version' not in ('1','2') or payload->'pointer'->'_sharedResearchObject'->>'id' !~ '^[a-f0-9]{64}$' or payload->'pointer'->'_sharedResearchObject'->>'rawSha256' !~ '^[a-f0-9]{64}$' then raise exception 'Verified object receipt required' using errcode='22023';end if;
 insert into public.football_learning_records(id,kind,sport,game_id,event_start,model_version,parent_id,mode,pointer,summary)
 values(payload->>'id',payload->>'kind',payload->>'sport',payload->>'gameId',at_time,payload->>'modelVersion',payload->>'parentId',m,payload->'pointer',payload->'summary') on conflict(id) do nothing;
 select * into r from public.football_learning_records where id=payload->>'id';return to_jsonb(r);
end$$;
revoke all on function gridiron_shared_private.learning_write(text,jsonb) from public,anon,authenticated;
grant usage on schema gridiron_shared_private to anon,authenticated;
grant execute on function gridiron_shared_private.learning_write(text,jsonb) to anon,authenticated;
create function public.gridiron_learning_write(token text,payload jsonb) returns jsonb language sql security invoker set search_path=pg_catalog as $$select gridiron_shared_private.learning_write(token,payload)$$;
revoke all on function public.gridiron_learning_write(text,jsonb) from public,anon,authenticated;
grant execute on function public.gridiron_learning_write(text,jsonb) to anon,authenticated;
comment on table public.football_learning_records is 'Immutable public NFL/CFB research references; private finances remain in existing owner-isolated tables. Payloads are checksummed compressed objects; no raw simulation games are duplicated here.';
