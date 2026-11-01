-- Immutable, per-owner probability observations. No existing table is rewritten.
create table public.probability_history(
 id text primary key check(id~'^[a-f0-9]{64}$'),user_id uuid not null default auth.uid() references auth.users(id) on delete cascade,
 target_key text not null check(length(target_key)=64),sport text not null check(sport in ('NFL','CFB')),
 evidence_key text not null check(length(evidence_key)=64),data jsonb not null check(jsonb_typeof(data)='object' and octet_length(data::text)<=1000000),
 proof jsonb not null,created_at timestamptz not null default now()
);
create index probability_history_owner_target_time on public.probability_history(user_id,target_key,created_at desc,id);
alter table public.probability_history enable row level security;
create policy owned_read on public.probability_history for select to authenticated using(user_id=(select auth.uid()));
create policy owned_append on public.probability_history for insert to authenticated with check(user_id=(select auth.uid()));
revoke all on public.probability_history from anon,authenticated;
grant select,insert on public.probability_history to authenticated;
