-- Additive, owner-scoped editable research. Existing ledger/prediction tables are untouched.
create table public.research_workspaces (
 id uuid primary key, user_id uuid not null references auth.users(id) on delete cascade,
 kind text not null check (kind in ('combination','research')), sport text not null check(sport in ('NFL','CFB')),
 revision integer not null check(revision>0), data jsonb not null check(jsonb_typeof(data)='object' and octet_length(data::text)<=100000),
 created_at timestamptz not null default now(), updated_at timestamptz not null default now(), unique(id,user_id)
);
create index research_workspaces_owner_updated on public.research_workspaces(user_id,updated_at desc,id);
create table public.research_workspace_versions (
 workspace_id uuid not null, user_id uuid not null, revision integer not null check(revision>0),
 mutation_id uuid not null, request_hash text not null, data jsonb not null,
 created_at timestamptz not null default now(), primary key(workspace_id,revision), unique(user_id,mutation_id),
 foreign key(workspace_id,user_id) references public.research_workspaces(id,user_id) on delete cascade
);
alter table public.research_workspaces enable row level security;
alter table public.research_workspace_versions enable row level security;
create policy owned_read on public.research_workspaces for select to authenticated using(user_id=(select auth.uid()));
create policy owned_read on public.research_workspace_versions for select to authenticated using(user_id=(select auth.uid()));
revoke all on public.research_workspaces,public.research_workspace_versions from anon,authenticated;
grant select on public.research_workspaces,public.research_workspace_versions to authenticated;
create or replace function gridiron_private.save_workspace(p jsonb) returns jsonb
language plpgsql security definer set search_path='' as $$
declare owner uuid:=auth.uid(); wid uuid; mutation uuid; expected integer; existing public.research_workspaces; prior public.research_workspace_versions; fingerprint text; v jsonb;
begin
 if owner is null then raise exception 'Sign in to save private research' using errcode='42501'; end if;
 if jsonb_typeof(p)<>'object' or jsonb_typeof(p->'data')<>'object' or octet_length(p::text)>110000 then raise exception 'Invalid research payload' using errcode='22023';end if;
 if p->>'kind' not in ('combination','research') or p->>'sport' not in ('NFL','CFB') or coalesce(p->>'kind','')='' or coalesce(p->>'sport','')='' then raise exception 'Invalid research kind or sport' using errcode='22023';end if;
 wid:=(p->>'id')::uuid;mutation:=(p->>'mutationId')::uuid;expected:=(p->>'expectedRevision')::integer;
 if wid is null or mutation is null or expected is null or expected<0 then raise exception 'Revision and mutation identity required' using errcode='22023';end if;
 fingerprint:=encode(sha256(convert_to(p::text,'UTF8')),'hex');
 -- Serialize creation and edits for this owner/workspace, including concurrent first saves.
 perform pg_advisory_xact_lock(hashtextextended(owner::text||wid::text,0));
 select * into prior from public.research_workspace_versions where user_id=owner and mutation_id=mutation;
 if found then
  if prior.workspace_id<>wid or prior.request_hash<>fingerprint then raise exception 'Idempotency key was reused with different content' using errcode='23505';end if;
  return jsonb_build_object('id',wid,'revision',prior.revision,'data',prior.data,'updated_at',prior.created_at,'idempotent',true);
 end if;
 select * into existing from public.research_workspaces where id=wid for update;
 if found then
  if existing.user_id<>owner then raise exception 'Research not found' using errcode='42501';end if;
  if existing.revision<>expected then raise exception 'A newer cloud revision exists. Reload before saving.' using errcode='40001';end if;
  if existing.kind<>p->>'kind' or existing.sport<>p->>'sport' then raise exception 'Create a separate workspace to change kind or sport' using errcode='22023';end if;
  update public.research_workspaces set data=p->'data',revision=revision+1,updated_at=clock_timestamp() where id=wid returning * into existing;
 else
  if expected<>0 then raise exception 'Cloud revision is missing; reload before saving' using errcode='40001';end if;
  insert into public.research_workspaces(id,user_id,kind,sport,revision,data) values(wid,owner,p->>'kind',p->>'sport',1,p->'data') returning * into existing;
 end if;
 insert into public.research_workspace_versions(workspace_id,user_id,revision,mutation_id,request_hash,data,created_at) values(wid,owner,existing.revision,mutation,fingerprint,existing.data,existing.updated_at);
 return to_jsonb(existing)-'user_id';
end $$;
revoke all on function gridiron_private.save_workspace(jsonb) from public,anon;
grant execute on function gridiron_private.save_workspace(jsonb) to authenticated;
create function public.gridiron_save_workspace(p jsonb) returns jsonb language sql security invoker set search_path='' as $$select gridiron_private.save_workspace(p)$$;
revoke all on function public.gridiron_save_workspace(jsonb) from public,anon;
grant execute on function public.gridiron_save_workspace(jsonb) to authenticated;
