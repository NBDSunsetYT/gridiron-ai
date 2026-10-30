-- GRIDIRON AI 4: additive cloud schema. Never replaces the existing SQLite database.
-- Money is exact integer cents in NUMERIC; all application data is owner-scoped.
create schema if not exists gridiron_private;
revoke all on schema gridiron_private from public, anon;
grant usage on schema gridiron_private to authenticated;

create table public.profiles (
 user_id uuid primary key default auth.uid() references auth.users(id) on delete cascade,
 email text,
 settings jsonb not null default '{"monthlyLimitCents":null,"timezone":"UTC","notifications":{},"theme":"dark"}'::jsonb check(jsonb_typeof(settings)='object'),
 created_at timestamptz not null default now(), updated_at timestamptz not null default now()
);
create table public.preferences(user_id uuid not null default auth.uid() references auth.users(id) on delete cascade,key text not null check(length(key) between 1 and 120),value jsonb not null,updated_at timestamptz not null default now(),primary key(user_id,key));
create table public.notification_settings(user_id uuid primary key default auth.uid() references auth.users(id) on delete cascade,categories jsonb not null default '{}'::jsonb,quiet_hours jsonb not null default '{}'::jsonb,updated_at timestamptz not null default now());
create table public.sportsbook_accounts(id uuid primary key default gen_random_uuid(),user_id uuid not null default auth.uid() references auth.users(id) on delete cascade,sportsbook text not null check(sportsbook in ('DraftKings','Hard Rock')),currency text not null default 'USD' check(currency='USD'),created_at timestamptz not null default now(),unique(user_id,sportsbook),unique(id,user_id));
create table public.ledger_entries(id uuid primary key default gen_random_uuid(),user_id uuid not null default auth.uid() references auth.users(id) on delete cascade,account_id uuid not null,type text not null check(type in ('starting_balance','deposit','withdrawal','transfer','promotional_credit','adjustment','refund','wager','settlement','reversal')),amount_cents numeric(20,0) not null,occurred_at timestamptz not null default now(),note text not null default '',reference text,related_id uuid,reverses_id uuid unique,created_at timestamptz not null default now(),unique(id,user_id),foreign key(account_id,user_id) references public.sportsbook_accounts(id,user_id),foreign key(reverses_id,user_id) references public.ledger_entries(id,user_id) deferrable initially deferred);
create unique index ledger_reference_owner on public.ledger_entries(user_id,reference) where reference is not null;
create index ledger_entries_owner_date on public.ledger_entries(user_id,occurred_at desc);
create table public.ledger_postings(id uuid primary key default gen_random_uuid(),user_id uuid not null default auth.uid() references auth.users(id) on delete cascade,entry_id uuid not null,account_id uuid not null,bucket text not null check(bucket in ('cash','escrow','capital','promotion','adjustment','betting_pnl')),amount_cents numeric(20,0) not null,foreign key(entry_id,user_id) references public.ledger_entries(id,user_id) on delete cascade,foreign key(account_id,user_id) references public.sportsbook_accounts(id,user_id));
create index ledger_postings_owner_bucket on public.ledger_postings(user_id,account_id,bucket);
create index ledger_postings_entry on public.ledger_postings(entry_id,user_id);
create table public.wagers(id uuid primary key default gen_random_uuid(),user_id uuid not null default auth.uid() references auth.users(id) on delete cascade,account_id uuid not null,event text not null,market text not null,selection text not null,odds integer not null check(abs(odds) between 100 and 100000),stake_cents numeric(20,0) not null check(stake_cents>0),placed_at timestamptz not null,settled_at timestamptz,result text not null default 'pending' check(result in ('pending','won','lost','voided','cashed_out')),payout_cents numeric(20,0) check(payout_cents>=0),notes text not null default '',prediction jsonb,legs jsonb,created_at timestamptz not null default now(),unique(id,user_id),foreign key(account_id,user_id) references public.sportsbook_accounts(id,user_id),check((result='pending' and settled_at is null and payout_cents is null) or (result<>'pending' and settled_at is not null and payout_cents is not null)),check(settled_at is null or settled_at>=placed_at));
create index wagers_owner_placement on public.wagers(user_id,placed_at desc);
create table public.wager_legs(id uuid primary key default gen_random_uuid(),user_id uuid not null default auth.uid() references auth.users(id) on delete cascade,wager_id uuid not null,ordinal integer not null check(ordinal between 1 and 12),selection text not null,market text,data jsonb not null default '{}'::jsonb,foreign key(wager_id,user_id) references public.wagers(id,user_id) on delete cascade,unique(wager_id,ordinal));
create table public.settlements(id uuid primary key default gen_random_uuid(),user_id uuid not null default auth.uid() references auth.users(id) on delete cascade,wager_id uuid not null unique,entry_id uuid not null,result text not null check(result in ('won','lost','voided','cashed_out')),payout_cents numeric(20,0) not null check(payout_cents>=0),settled_at timestamptz not null,foreign key(wager_id,user_id) references public.wagers(id,user_id) on delete cascade,foreign key(entry_id,user_id) references public.ledger_entries(id,user_id));
create table public.reconciliation_records(id uuid primary key default gen_random_uuid(),user_id uuid not null default auth.uid() references auth.users(id) on delete cascade,account_id uuid not null,statement_balance_cents numeric(20,0) not null,recorded_balance_cents numeric(20,0) not null,difference_cents numeric(20,0) not null,note text not null default '',created_at timestamptz not null default now(),foreign key(account_id,user_id) references public.sportsbook_accounts(id,user_id));
create table public.audit_log(id uuid primary key default gen_random_uuid(),user_id uuid not null default auth.uid() references auth.users(id) on delete cascade,action text not null,entity_id uuid,detail jsonb not null default '{}'::jsonb,created_at timestamptz not null default now());
create index audit_log_owner_date on public.audit_log(user_id,created_at desc);
create table public.data_imports(id uuid primary key default gen_random_uuid(),user_id uuid not null default auth.uid() references auth.users(id) on delete cascade,source_hash text not null,kind text not null,row_count integer not null check(row_count>=0),created_at timestamptz not null default now(),unique(user_id,source_hash,kind));
create table public.rate_limit_buckets(user_id uuid not null default auth.uid() references auth.users(id) on delete cascade,key text not null,count integer not null check(count>=0),reset_at timestamptz not null,primary key(user_id,key));
create table public.conversations(id uuid primary key default gen_random_uuid(),user_id uuid not null default auth.uid() references auth.users(id) on delete cascade,title text not null check(length(title) between 1 and 200),created_at timestamptz not null default now(),updated_at timestamptz not null default now(),unique(id,user_id));
create index conversations_owner_date on public.conversations(user_id,updated_at desc);
create table public.conversation_messages(id uuid primary key default gen_random_uuid(),user_id uuid not null default auth.uid() references auth.users(id) on delete cascade,conversation_id uuid not null,role text not null check(role in ('user','assistant')),content text not null check(length(content) between 1 and 100000),data jsonb not null default '{}'::jsonb,created_at timestamptz not null default now(),foreign key(conversation_id,user_id) references public.conversations(id,user_id) on delete cascade);
create index conversation_messages_owner_thread on public.conversation_messages(user_id,conversation_id,created_at);
create table public.watchlists(id uuid primary key default gen_random_uuid(),user_id uuid not null default auth.uid() references auth.users(id) on delete cascade,name text not null,items jsonb not null default '[]'::jsonb,created_at timestamptz not null default now(),updated_at timestamptz not null default now());
create table public.saved_research(id uuid primary key default gen_random_uuid(),user_id uuid not null default auth.uid() references auth.users(id) on delete cascade,title text not null,kind text not null,data jsonb not null,source text not null,observed_at timestamptz not null,available_at timestamptz,version text not null,reliability_status text not null check(reliability_status in ('verified','user_attested','unverified','incomplete')),created_at timestamptz not null default now());
create table public.gridiron_records(id uuid primary key default gen_random_uuid(),user_id uuid not null default auth.uid() references auth.users(id) on delete cascade,kind text not null check(length(kind) between 1 and 120),entity_key text not null default '',data jsonb not null,source text not null default 'user',observed_at timestamptz not null default now(),available_at timestamptz,version text not null default '1',created_at timestamptz not null default now(),updated_at timestamptz not null default now(),unique(id,user_id));
create index gridiron_records_owner_kind on public.gridiron_records(user_id,kind,created_at desc);
create index gridiron_records_owner_entity on public.gridiron_records(user_id,kind,entity_key);

-- Relational, provenance-bearing NFL warehouse. Tables are private to each importing account.
create table public.nfl_seasons(id uuid primary key default gen_random_uuid(),user_id uuid not null default auth.uid() references auth.users(id) on delete cascade,season integer not null check(season between 1920 and 2200),source text not null,collected_at timestamptz not null default now(),event_at timestamptz not null,available_at timestamptz,version text not null,reliability_status text not null,unique(user_id,season),unique(id,user_id));
create table public.nfl_teams(id uuid primary key default gen_random_uuid(),user_id uuid not null default auth.uid() references auth.users(id) on delete cascade,external_id text not null,abbreviation text not null,name text not null,source text not null,collected_at timestamptz not null default now(),event_at timestamptz not null,available_at timestamptz,version text not null,reliability_status text not null,unique(user_id,external_id),unique(id,user_id));
create table public.nfl_players(id uuid primary key default gen_random_uuid(),user_id uuid not null default auth.uid() references auth.users(id) on delete cascade,external_id text not null,team_id uuid,name text not null,position text,source text not null,collected_at timestamptz not null default now(),event_at timestamptz not null,available_at timestamptz,version text not null,reliability_status text not null,unique(user_id,external_id),unique(id,user_id),foreign key(team_id,user_id) references public.nfl_teams(id,user_id));
create table public.nfl_games(id uuid primary key default gen_random_uuid(),user_id uuid not null default auth.uid() references auth.users(id) on delete cascade,external_id text not null,season_id uuid not null,home_team_id uuid not null,away_team_id uuid not null,kickoff_at timestamptz not null,status text not null,home_score integer check(home_score>=0),away_score integer check(away_score>=0),source text not null,collected_at timestamptz not null default now(),event_at timestamptz not null,available_at timestamptz,version text not null,reliability_status text not null,unique(user_id,external_id),unique(id,user_id),foreign key(season_id,user_id) references public.nfl_seasons(id,user_id),foreign key(home_team_id,user_id) references public.nfl_teams(id,user_id),foreign key(away_team_id,user_id) references public.nfl_teams(id,user_id),check(home_team_id<>away_team_id));
create table public.nfl_plays(id uuid primary key default gen_random_uuid(),user_id uuid not null default auth.uid() references auth.users(id) on delete cascade,game_id uuid not null,external_id text not null,offense_team_id uuid,defense_team_id uuid,passer_id uuid,receiver_id uuid,rusher_id uuid,play_type text not null,down smallint check(down between 1 and 4),distance numeric,yardline numeric,epa numeric,success boolean,data jsonb not null,source text not null,collected_at timestamptz not null default now(),event_at timestamptz not null,available_at timestamptz,version text not null,reliability_status text not null,unique(user_id,game_id,external_id),foreign key(game_id,user_id) references public.nfl_games(id,user_id),foreign key(offense_team_id,user_id) references public.nfl_teams(id,user_id),foreign key(defense_team_id,user_id) references public.nfl_teams(id,user_id),foreign key(passer_id,user_id) references public.nfl_players(id,user_id),foreign key(receiver_id,user_id) references public.nfl_players(id,user_id),foreign key(rusher_id,user_id) references public.nfl_players(id,user_id));
create table public.team_statistics(id uuid primary key default gen_random_uuid(),user_id uuid not null default auth.uid() references auth.users(id) on delete cascade,team_id uuid not null,game_id uuid,metrics jsonb not null,sample_size integer not null check(sample_size>=0),source text not null,collected_at timestamptz not null default now(),event_at timestamptz not null,available_at timestamptz,version text not null,reliability_status text not null,foreign key(team_id,user_id) references public.nfl_teams(id,user_id),foreign key(game_id,user_id) references public.nfl_games(id,user_id));
create table public.player_statistics(id uuid primary key default gen_random_uuid(),user_id uuid not null default auth.uid() references auth.users(id) on delete cascade,player_id uuid not null,game_id uuid,metrics jsonb not null,sample_size integer not null check(sample_size>=0),source text not null,collected_at timestamptz not null default now(),event_at timestamptz not null,available_at timestamptz,version text not null,reliability_status text not null,foreign key(player_id,user_id) references public.nfl_players(id,user_id),foreign key(game_id,user_id) references public.nfl_games(id,user_id));
create table public.player_usage(id uuid primary key default gen_random_uuid(),user_id uuid not null default auth.uid() references auth.users(id) on delete cascade,player_id uuid not null,game_id uuid,snaps integer check(snaps>=0),routes integer check(routes>=0),targets integer check(targets>=0),carries integer check(carries>=0),snap_share numeric check(snap_share between 0 and 1),route_share numeric check(route_share between 0 and 1),target_share numeric check(target_share between 0 and 1),source text not null,collected_at timestamptz not null default now(),event_at timestamptz not null,available_at timestamptz,version text not null,reliability_status text not null,foreign key(player_id,user_id) references public.nfl_players(id,user_id),foreign key(game_id,user_id) references public.nfl_games(id,user_id));
create table public.depth_charts(id uuid primary key default gen_random_uuid(),user_id uuid not null default auth.uid() references auth.users(id) on delete cascade,team_id uuid not null,player_id uuid not null,position text not null,depth integer not null check(depth>0),source text not null,collected_at timestamptz not null default now(),event_at timestamptz not null,available_at timestamptz,version text not null,reliability_status text not null,foreign key(team_id,user_id) references public.nfl_teams(id,user_id),foreign key(player_id,user_id) references public.nfl_players(id,user_id));
create table public.coaching_tendencies(id uuid primary key default gen_random_uuid(),user_id uuid not null default auth.uid() references auth.users(id) on delete cascade,team_id uuid not null,coach text,metrics jsonb not null,sample_size integer not null check(sample_size>=0),source text not null,collected_at timestamptz not null default now(),event_at timestamptz not null,available_at timestamptz,version text not null,reliability_status text not null,foreign key(team_id,user_id) references public.nfl_teams(id,user_id));
create table public.injury_reports(id uuid primary key default gen_random_uuid(),user_id uuid not null default auth.uid() references auth.users(id) on delete cascade,player_id uuid,game_id uuid,status text not null,practice_participation text,availability jsonb,data jsonb not null,source text not null,collected_at timestamptz not null default now(),event_at timestamptz not null,available_at timestamptz,version text not null,reliability_status text not null,foreign key(player_id,user_id) references public.nfl_players(id,user_id),foreign key(game_id,user_id) references public.nfl_games(id,user_id));
create table public.weather_reports(id uuid primary key default gen_random_uuid(),user_id uuid not null default auth.uid() references auth.users(id) on delete cascade,game_id uuid not null,temperature_c numeric,wind_kph numeric check(wind_kph>=0),precipitation_mm numeric check(precipitation_mm>=0),data jsonb not null,source text not null,collected_at timestamptz not null default now(),event_at timestamptz not null,available_at timestamptz,version text not null,reliability_status text not null,foreign key(game_id,user_id) references public.nfl_games(id,user_id));
create table public.market_providers(id uuid primary key default gen_random_uuid(),user_id uuid not null default auth.uid() references auth.users(id) on delete cascade,name text not null,authorization_basis text not null,status text not null,created_at timestamptz not null default now(),unique(id,user_id));
create table public.market_events(id uuid primary key default gen_random_uuid(),user_id uuid not null default auth.uid() references auth.users(id) on delete cascade,provider_id uuid,external_id text not null,game_id uuid,name text not null,event_at timestamptz not null,source text not null,collected_at timestamptz not null default now(),available_at timestamptz,version text not null,reliability_status text not null,unique(id,user_id),unique(user_id,external_id),foreign key(provider_id,user_id) references public.market_providers(id,user_id),foreign key(game_id,user_id) references public.nfl_games(id,user_id));
create table public.market_contracts(id uuid primary key default gen_random_uuid(),user_id uuid not null default auth.uid() references auth.users(id) on delete cascade,event_id uuid not null,external_id text not null,player_id uuid,team_id uuid,market_type text not null,threshold numeric,operator text,settlement_rules jsonb not null,source text not null,collected_at timestamptz not null default now(),event_at timestamptz not null,available_at timestamptz,version text not null,reliability_status text not null,unique(user_id,external_id),unique(id,user_id),foreign key(event_id,user_id) references public.market_events(id,user_id),foreign key(player_id,user_id) references public.nfl_players(id,user_id),foreign key(team_id,user_id) references public.nfl_teams(id,user_id));
create table public.contract_quotes(id uuid primary key default gen_random_uuid(),user_id uuid not null default auth.uid() references auth.users(id) on delete cascade,contract_id uuid not null,yes_bid numeric(12,6) check(yes_bid between 0 and 100),yes_ask numeric(12,6) check(yes_ask between 0 and 100),no_bid numeric(12,6) check(no_bid between 0 and 100),no_ask numeric(12,6) check(no_ask between 0 and 100),liquidity numeric check(liquidity>=0),fees jsonb not null,quoted_at timestamptz not null,source text not null,collected_at timestamptz not null default now(),available_at timestamptz,version text not null,reliability_status text not null,foreign key(contract_id,user_id) references public.market_contracts(id,user_id),check(yes_bid is null or yes_ask is null or yes_bid<=yes_ask),check(no_bid is null or no_ask is null or no_bid<=no_ask));
create table public.contract_outcomes(id uuid primary key default gen_random_uuid(),user_id uuid not null default auth.uid() references auth.users(id) on delete cascade,contract_id uuid not null,outcome text not null check(outcome in ('YES','NO','VOID')),settled_at timestamptz not null,source text not null,collected_at timestamptz not null default now(),available_at timestamptz,version text not null,reliability_status text not null,unique(user_id,contract_id),foreign key(contract_id,user_id) references public.market_contracts(id,user_id));
create table public.model_versions(id uuid primary key default gen_random_uuid(),user_id uuid not null default auth.uid() references auth.users(id) on delete cascade,name text not null,version text not null,method text not null,artifact jsonb,source text not null,created_at timestamptz not null default now(),unique(user_id,name,version),unique(id,user_id));
create table public.feature_snapshots(id uuid primary key default gen_random_uuid(),user_id uuid not null default auth.uid() references auth.users(id) on delete cascade,game_id uuid,features jsonb not null,as_of timestamptz not null,source text not null,collected_at timestamptz not null default now(),available_at timestamptz,version text not null,reliability_status text not null,unique(id,user_id),foreign key(game_id,user_id) references public.nfl_games(id,user_id));
create table public.training_runs(id uuid primary key default gen_random_uuid(),user_id uuid not null default auth.uid() references auth.users(id) on delete cascade,model_version_id uuid not null,cutoff_at timestamptz not null,dataset_hash text not null,parameters jsonb not null,metrics jsonb not null,created_at timestamptz not null default now(),unique(id,user_id),foreign key(model_version_id,user_id) references public.model_versions(id,user_id));
create table public.simulation_runs(id uuid primary key default gen_random_uuid(),user_id uuid not null default auth.uid() references auth.users(id) on delete cascade,game_id uuid,model_version_id uuid,feature_snapshot_id uuid,status text not null check(status in ('queued','running','completed','failed','blocked')),simulation_count integer not null check(simulation_count between 1 and 1000000),seed bigint not null,inputs jsonb not null,summary jsonb,started_at timestamptz,completed_at timestamptz,created_at timestamptz not null default now(),unique(id,user_id),foreign key(game_id,user_id) references public.nfl_games(id,user_id),foreign key(model_version_id,user_id) references public.model_versions(id,user_id),foreign key(feature_snapshot_id,user_id) references public.feature_snapshots(id,user_id));
create table public.simulation_scenarios(id uuid primary key default gen_random_uuid(),user_id uuid not null default auth.uid() references auth.users(id) on delete cascade,simulation_run_id uuid not null,name text not null,weight numeric not null check(weight between 0 and 1),assumptions jsonb not null,summary jsonb,created_at timestamptz not null default now(),foreign key(simulation_run_id,user_id) references public.simulation_runs(id,user_id) on delete cascade);
create table public.probability_distributions(id uuid primary key default gen_random_uuid(),user_id uuid not null default auth.uid() references auth.users(id) on delete cascade,simulation_run_id uuid not null,entity text not null,statistic text not null,distribution jsonb not null,uncertainty jsonb not null,created_at timestamptz not null default now(),foreign key(simulation_run_id,user_id) references public.simulation_runs(id,user_id) on delete cascade);
create table public.model_predictions(id uuid primary key default gen_random_uuid(),user_id uuid not null default auth.uid() references auth.users(id) on delete cascade,contract_id uuid,game_id uuid,model_version_id uuid,feature_snapshot_id uuid,simulation_run_id uuid,probability numeric not null check(probability between 0 and 1),as_of timestamptz not null,event_start timestamptz not null,market_snapshot jsonb not null,injury_assumptions jsonb not null,weather_assumptions jsonb not null,uncertainty jsonb not null,created_at timestamptz not null default now(),unique(id,user_id),foreign key(contract_id,user_id) references public.market_contracts(id,user_id),foreign key(game_id,user_id) references public.nfl_games(id,user_id),foreign key(model_version_id,user_id) references public.model_versions(id,user_id),foreign key(feature_snapshot_id,user_id) references public.feature_snapshots(id,user_id),foreign key(simulation_run_id,user_id) references public.simulation_runs(id,user_id),check(as_of<event_start));
create table public.backtests(id uuid primary key default gen_random_uuid(),user_id uuid not null default auth.uid() references auth.users(id) on delete cascade,model_version_id uuid,cutoff_at timestamptz not null,validation_start timestamptz not null,validation_end timestamptz not null,dataset_hash text not null,sample_size integer not null check(sample_size>=0),metrics jsonb not null,promotion_status text not null default 'not_promoted',created_at timestamptz not null default now(),unique(id,user_id),foreign key(model_version_id,user_id) references public.model_versions(id,user_id),check(cutoff_at<=validation_start and validation_start<=validation_end));
create table public.calibration_metrics(id uuid primary key default gen_random_uuid(),user_id uuid not null default auth.uid() references auth.users(id) on delete cascade,backtest_id uuid not null,bucket_low numeric not null check(bucket_low between 0 and 1),bucket_high numeric not null check(bucket_high between 0 and 1),sample_size integer not null check(sample_size>=0),predicted numeric,observed numeric,interval jsonb,created_at timestamptz not null default now(),foreign key(backtest_id,user_id) references public.backtests(id,user_id),check(bucket_low<bucket_high));
create table public.prediction_audits(id uuid primary key default gen_random_uuid(),user_id uuid not null default auth.uid() references auth.users(id) on delete cascade,prediction_id uuid not null,status text not null,checks jsonb not null,withheld boolean not null,created_at timestamptz not null default now(),foreign key(prediction_id,user_id) references public.model_predictions(id,user_id));
create table public.saved_reports(id uuid primary key default gen_random_uuid(),user_id uuid not null default auth.uid() references auth.users(id) on delete cascade,title text not null,content jsonb not null,sources jsonb not null,created_at timestamptz not null default now());
create table public.paper_positions(id uuid primary key default gen_random_uuid(),user_id uuid not null default auth.uid() references auth.users(id) on delete cascade,contract_id uuid,prediction_id uuid,quantity numeric not null check(quantity>0),side text not null check(side in ('YES','NO')),entry_price_cents numeric not null check(entry_price_cents between 0 and 100),fees jsonb not null,status text not null default 'open',result jsonb,created_at timestamptz not null default now(),foreign key(contract_id,user_id) references public.market_contracts(id,user_id),foreign key(prediction_id,user_id) references public.model_predictions(id,user_id));

-- Authentication sessions live in Supabase Auth's auth.sessions, never a publicly exposed duplicate.
-- RLS is enabled on EVERY public table; none of these datasets are anonymous/public.
do $$
declare t text;begin
 for t in select tablename from pg_tables where schemaname='public' and tablename in ('profiles','preferences','notification_settings','sportsbook_accounts','ledger_entries','ledger_postings','wagers','wager_legs','settlements','reconciliation_records','audit_log','data_imports','rate_limit_buckets','conversations','conversation_messages','watchlists','saved_research','gridiron_records','nfl_seasons','nfl_teams','nfl_players','nfl_games','nfl_plays','team_statistics','player_statistics','player_usage','depth_charts','coaching_tendencies','injury_reports','weather_reports','market_providers','market_events','market_contracts','contract_quotes','contract_outcomes','model_versions','feature_snapshots','training_runs','simulation_runs','simulation_scenarios','probability_distributions','model_predictions','backtests','calibration_metrics','prediction_audits','saved_reports','paper_positions') loop
  execute format('alter table public.%I enable row level security',t);
  execute format('create policy own_rows on public.%I for all to authenticated using ((select auth.uid())=user_id) with check ((select auth.uid())=user_id)',t);
  execute format('revoke all on public.%I from anon,authenticated',t);
  execute format('grant select,insert,update,delete on public.%I to authenticated',t);
  execute format('create index if not exists %I on public.%I(user_id)',t||'_owner_idx',t);
 end loop;
end $$;
revoke insert,update,delete on public.sportsbook_accounts,public.ledger_entries,public.ledger_postings,public.wagers,public.wager_legs,public.settlements,public.audit_log,public.data_imports,public.rate_limit_buckets from authenticated;

create function gridiron_private.immutable_row() returns trigger language plpgsql set search_path='' as $$begin raise exception 'Historical rows are immutable; append a correction/version' using errcode='22023';end$$;
create trigger ledger_entries_immutable before update on public.ledger_entries for each row execute function gridiron_private.immutable_row();
create trigger ledger_postings_immutable before update on public.ledger_postings for each row execute function gridiron_private.immutable_row();
create trigger settlements_immutable before update on public.settlements for each row execute function gridiron_private.immutable_row();
create trigger audit_log_immutable before update on public.audit_log for each row execute function gridiron_private.immutable_row();
create trigger quote_immutable before update on public.contract_quotes for each row execute function gridiron_private.immutable_row();
create trigger prediction_immutable before update on public.model_predictions for each row execute function gridiron_private.immutable_row();
create trigger outcome_immutable before update on public.contract_outcomes for each row execute function gridiron_private.immutable_row();
create trigger plays_immutable before update on public.nfl_plays for each row execute function gridiron_private.immutable_row();
create function gridiron_private.immutable_record() returns trigger language plpgsql set search_path='' as $$begin
 if old.kind in ('contract_quotes','prediction_snapshots','contract_settlements','injury_history','simulation_inputs','warehouse_records') and (tg_op='UPDATE' or current_user='authenticated') then raise exception 'Historical records are immutable; append a new version' using errcode='22023';end if;if tg_op='DELETE' then return old;end if;return new;end$$;
create trigger gridiron_record_immutable before update or delete on public.gridiron_records for each row execute function gridiron_private.immutable_record();

create function gridiron_private.owner_id() returns uuid language plpgsql stable security definer set search_path='' as $$declare u uuid:=auth.uid();s text:=auth.jwt()->>'session_id';begin if u is null then raise exception 'Authentication required' using errcode='28000';end if;if s is not null and not exists(select 1 from auth.sessions where id=s::uuid and user_id=u) then raise exception 'Session was revoked; sign in again' using errcode='28000';end if;return u;end$$;
create function gridiron_private.amount(value text,allow_zero boolean default false) returns numeric language plpgsql immutable security invoker set search_path='' as $$declare n numeric;begin
 if value is null or value!~'^-?[0-9]+([.][0-9]{1,2})?$' then raise exception 'Amounts require exact dollars with at most two decimals' using errcode='22023';end if;n:=value::numeric*100;
 if abs(n)>100000000000 or (n=0 and not allow_zero) then raise exception 'Amount outside supported range' using errcode='22023';end if;return n;end$$;
create function gridiron_private.ensure_accounts() returns void language plpgsql security definer set search_path='' as $$declare u uuid:=gridiron_private.owner_id();begin
 insert into public.profiles(user_id,email) values(u,auth.jwt()->>'email') on conflict(user_id) do nothing;
 insert into public.sportsbook_accounts(user_id,sportsbook) values(u,'DraftKings'),(u,'Hard Rock') on conflict(user_id,sportsbook) do nothing;
end$$;
create function gridiron_private.account_id(book text) returns uuid language plpgsql security definer set search_path='' as $$declare u uuid:=gridiron_private.owner_id();a uuid;begin
 if book not in ('DraftKings','Hard Rock') or book is null then raise exception 'Choose DraftKings or Hard Rock' using errcode='22023';end if;
 perform gridiron_private.ensure_accounts();select id into a from public.sportsbook_accounts where user_id=u and sportsbook=book;return a;end$$;
create function gridiron_private.balance(a uuid,b text default 'cash') returns numeric language sql stable security definer set search_path='' as $$select coalesce(sum(amount_cents),0) from public.ledger_postings where user_id=auth.uid() and account_id=a and bucket=b$$;
create function gridiron_private.write_entry(p jsonb,postings jsonb) returns uuid language plpgsql security definer set search_path='' as $$declare u uuid:=gridiron_private.owner_id();j uuid:=coalesce(nullif(p->>'id','')::uuid,gen_random_uuid());line jsonb;tot numeric:=0;amt numeric;aid uuid;bucket_name text;begin
 if jsonb_typeof(postings)<>'array' or jsonb_array_length(postings)<2 then raise exception 'At least two balanced postings required' using errcode='22023';end if;
 for line in select value from jsonb_array_elements(postings) loop tot:=tot+(line->>'amount')::numeric;end loop;
 if tot<>0 then raise exception 'Unbalanced entry rejected' using errcode='22023';end if;
 insert into public.ledger_entries(id,user_id,account_id,type,amount_cents,occurred_at,note,reference,related_id,reverses_id) values(j,u,(p->>'account_id')::uuid,p->>'type',(p->>'amount')::numeric,(p->>'date')::timestamptz,coalesce(p->>'note',''),nullif(p->>'reference',''),nullif(p->>'related_id','')::uuid,nullif(p->>'reverses_id','')::uuid);
 for line in select value from jsonb_array_elements(postings) loop
  aid:=(line->>'account_id')::uuid;bucket_name:=line->>'bucket';amt:=(line->>'amount')::numeric;
  if not exists(select 1 from public.sportsbook_accounts where id=aid and user_id=u) then raise exception 'Account not found' using errcode='22023';end if;
  if amt<>trunc(amt) or abs(gridiron_private.balance(aid,bucket_name)+amt)>9000000000000000 then raise exception 'Posting exceeds exact range' using errcode='22023';end if;
  insert into public.ledger_postings(user_id,entry_id,account_id,bucket,amount_cents) values(u,j,aid,bucket_name,amt);
 end loop;
 insert into public.audit_log(user_id,action,entity_id,detail) values(u,case when p?'reverses_id' then 'reverse' else 'create' end,j,p);
 return j;end$$;

create function gridiron_private.post_transaction(payload jsonb) returns jsonb language plpgsql security definer set search_path='' as $$
declare u uuid:=gridiron_private.owner_id();a uuid;target uuid;n numeric;delta numeric;t text:=payload->>'type';at_time timestamptz:=coalesce(nullif(payload->>'date','')::timestamptz,now());j uuid;bucket_name text;begin
 perform pg_advisory_xact_lock(hashtextextended(u::text,0));a:=gridiron_private.account_id(payload->>'sportsbook');n:=gridiron_private.amount(payload->>'amount');
 if t not in ('starting_balance','deposit','withdrawal','transfer','promotional_credit','adjustment','refund') or t is null then raise exception 'Unsupported transaction type' using errcode='22023';end if;
 if (t<>'adjustment' and n<0) or at_time>now()+interval '1 minute' then raise exception 'Invalid amount or future timestamp' using errcode='22023';end if;
 if length(coalesce(payload->>'note',''))>2000 or length(coalesce(payload->>'reference',''))>200 then raise exception 'Note/reference too long' using errcode='22023';end if;
 if t='starting_balance' and exists(select 1 from public.ledger_entries e where e.user_id=u and e.account_id=a and e.type=t and not exists(select 1 from public.ledger_entries r where r.user_id=u and r.reverses_id=e.id)) then raise exception 'Starting balance already recorded' using errcode='23505';end if;
 if t='transfer' then
  target:=gridiron_private.account_id(payload->>'toSportsbook');if target=a then raise exception 'Choose a different destination' using errcode='22023';end if;
  if gridiron_private.balance(a)<n then raise exception 'Insufficient available balance' using errcode='22023';end if;
  j:=gridiron_private.write_entry(jsonb_build_object('account_id',a,'type',t,'amount',n,'date',at_time,'note',coalesce(payload->>'note','Transfer'),'reference',payload->>'reference'),jsonb_build_array(jsonb_build_object('account_id',a,'bucket','cash','amount',-n),jsonb_build_object('account_id',target,'bucket','cash','amount',n)));
 else
  delta:=case when t='withdrawal' then -n else n end;
  if delta<0 and gridiron_private.balance(a)<-delta then raise exception 'Insufficient available balance' using errcode='22023';end if;
  bucket_name:=case when t='promotional_credit' then 'promotion' when t in ('adjustment','refund') then 'adjustment' else 'capital' end;
  j:=gridiron_private.write_entry(jsonb_build_object('account_id',a,'type',t,'amount',n,'date',at_time,'note',coalesce(payload->>'note',''),'reference',payload->>'reference'),jsonb_build_array(jsonb_build_object('account_id',a,'bucket','cash','amount',delta),jsonb_build_object('account_id',a,'bucket',bucket_name,'amount',-delta)));
 end if;
 return jsonb_build_object('id',j,'type',t,'sportsbook',payload->>'sportsbook','amountCents',n,'amount',(n/100)::numeric(20,2)::text,'date',at_time);
end$$;

create function gridiron_private.place_bet(payload jsonb) returns jsonb language plpgsql security definer set search_path='' as $$
declare u uuid:=gridiron_private.owner_id();a uuid;n numeric;odds_value integer;placed timestamptz:=coalesce(nullif(coalesce(payload->>'placementTime',payload->>'placedAt',payload->>'date'),'')::timestamptz,now());w uuid:=gen_random_uuid();j uuid;settings_value jsonb;tz text;lim numeric;spent numeric;leg jsonb;idx integer:=0;begin
 perform pg_advisory_xact_lock(hashtextextended(u::text,0));a:=gridiron_private.account_id(payload->>'sportsbook');n:=gridiron_private.amount(payload->>'stake');odds_value:=(payload->>'odds')::integer;
 if n<=0 or abs(odds_value) not between 100 and 100000 or odds_value is null then raise exception 'Invalid stake or American odds' using errcode='22023';end if;
 if gridiron_private.balance(a)<n then raise exception 'Insufficient available balance' using errcode='22023';end if;
 if length(trim(coalesce(payload->>'event',''))) not between 1 and 300 or length(trim(coalesce(payload->>'market',''))) not between 1 and 200 or length(trim(coalesce(payload->>'selection',''))) not between 1 and 500 or placed>now()+interval '1 minute' then raise exception 'Event, market, selection and valid placement required' using errcode='22023';end if;
 select settings into settings_value from public.profiles where user_id=u;tz:=coalesce(settings_value->>'timezone','UTC');lim:=(settings_value->>'monthlyLimitCents')::numeric;
 if lim is not null then select coalesce(sum(stake_cents),0) into spent from public.wagers where user_id=u and date_trunc('month',placed_at at time zone tz)=date_trunc('month',placed at time zone tz);if spent+n>lim then raise exception 'Monthly stake limit exceeded' using errcode='22023';end if;end if;
 if payload?'legs' and payload->'legs'<>'null'::jsonb and (jsonb_typeof(payload->'legs')<>'array' or jsonb_array_length(payload->'legs') not between 2 and 12) then raise exception 'Parlays need 2-12 legs' using errcode='22023';end if;
 insert into public.wagers(id,user_id,account_id,event,market,selection,odds,stake_cents,placed_at,notes,prediction,legs) values(w,u,a,trim(payload->>'event'),trim(payload->>'market'),trim(payload->>'selection'),odds_value,n,placed,coalesce(payload->>'notes',payload->>'note',''),payload->'prediction',payload->'legs');
 if jsonb_typeof(payload->'legs')='array' then for leg in select value from jsonb_array_elements(payload->'legs') loop idx:=idx+1;insert into public.wager_legs(user_id,wager_id,ordinal,selection,market,data) values(u,w,idx,coalesce(leg->>'selection','Recorded leg'),leg->>'market',leg);end loop;end if;
 j:=gridiron_private.write_entry(jsonb_build_object('account_id',a,'type','wager','amount',n,'date',placed,'note',payload->>'selection','related_id',w),jsonb_build_array(jsonb_build_object('account_id',a,'bucket','cash','amount',-n),jsonb_build_object('account_id',a,'bucket','escrow','amount',n)));
 return jsonb_build_object('id',w,'result','pending','stakeCents',n,'stake',(n/100)::numeric(20,2)::text);
end$$;

create function gridiron_private.settle_bet(payload jsonb) returns jsonb language plpgsql security definer set search_path='' as $$
declare u uuid:=gridiron_private.owner_id();b public.wagers%rowtype;result_value text:=payload->>'result';payout numeric;j uuid;at_time timestamptz:=coalesce(nullif(coalesce(payload->>'settlementTime',payload->>'settledAt',payload->>'date'),'')::timestamptz,now());begin
 perform pg_advisory_xact_lock(hashtextextended(u::text,0));select * into b from public.wagers where id=(payload->>'id')::uuid and user_id=u for update;
 if not found then raise exception 'Wager not found' using errcode='P0002';end if;if b.result<>'pending' then raise exception 'Wager already settled' using errcode='23505';end if;
 if result_value not in ('won','lost','voided','cashed_out') or result_value is null or at_time<b.placed_at or at_time>now()+interval '1 minute' then raise exception 'Invalid settlement result/time' using errcode='22023';end if;
 if result_value='lost' then payout:=0;if nullif(payload->>'payout','') is not null and gridiron_private.amount(payload->>'payout',true)<>0 then raise exception 'Lost wager payout must be zero' using errcode='22023';end if;
 elsif result_value='voided' then payout:=b.stake_cents;if nullif(payload->>'payout','') is not null and gridiron_private.amount(payload->>'payout',true)<>payout then raise exception 'Void must return exactly the stake' using errcode='22023';end if;
 elsif nullif(payload->>'payout','') is not null then payout:=gridiron_private.amount(payload->>'payout',true);
 elsif result_value='cashed_out' then raise exception 'Actual cash-out payout required' using errcode='22023';
 else payout:=round(b.stake_cents*(1+case when b.odds>0 then b.odds::numeric/100 else 100::numeric/(-b.odds) end));end if;
 if payout<0 or payout>100000000000 or (result_value='won' and payout<b.stake_cents) then raise exception 'Invalid total payout including returned stake' using errcode='22023';end if;
 update public.wagers set result=result_value,payout_cents=payout,settled_at=at_time where id=b.id and user_id=u;
 j:=gridiron_private.write_entry(jsonb_build_object('account_id',b.account_id,'type','settlement','amount',payout,'date',at_time,'note',result_value,'related_id',b.id),jsonb_build_array(jsonb_build_object('account_id',b.account_id,'bucket','escrow','amount',-b.stake_cents),jsonb_build_object('account_id',b.account_id,'bucket','cash','amount',payout),jsonb_build_object('account_id',b.account_id,'bucket','betting_pnl','amount',b.stake_cents-payout)));
 insert into public.settlements(user_id,wager_id,entry_id,result,payout_cents,settled_at) values(u,b.id,j,result_value,payout,at_time);
 return jsonb_build_object('id',b.id,'result',result_value,'payoutCents',payout,'payout',(payout/100)::numeric(20,2)::text,'profitCents',payout-b.stake_cents);
end$$;

create function gridiron_private.reverse_transaction(payload jsonb) returns jsonb language plpgsql security definer set search_path='' as $$
declare u uuid:=gridiron_private.owner_id();e public.ledger_entries%rowtype;p record;lines jsonb:='[]'::jsonb;j uuid;begin
 perform pg_advisory_xact_lock(hashtextextended(u::text,0));select * into e from public.ledger_entries where id=(payload->>'id')::uuid and user_id=u;
 if not found then raise exception 'Transaction not found' using errcode='P0002';end if;
 if e.type in ('wager','settlement','reversal') or exists(select 1 from public.ledger_entries where user_id=u and reverses_id=e.id) then raise exception 'Transaction cannot be reversed here or already reversed' using errcode='22023';end if;
 for p in select * from public.ledger_postings where user_id=u and entry_id=e.id loop
  if p.bucket='cash' and p.amount_cents>0 and gridiron_private.balance(p.account_id)<p.amount_cents then raise exception 'Insufficient available balance for reversal' using errcode='22023';end if;
  lines:=lines||jsonb_build_array(jsonb_build_object('account_id',p.account_id,'bucket',p.bucket,'amount',-p.amount_cents));
 end loop;
 j:=gridiron_private.write_entry(jsonb_build_object('account_id',e.account_id,'type','reversal','amount',-e.amount_cents,'date',now(),'note',coalesce(payload->>'note','Correction reversal'),'reverses_id',e.id),lines);
 return jsonb_build_object('id',j,'type','reversal','amountCents',-e.amount_cents);
end$$;

create function gridiron_private.update_settings(payload jsonb) returns jsonb language plpgsql security definer set search_path='' as $$declare u uuid:=gridiron_private.owner_id();s jsonb;tz text;begin
 perform gridiron_private.ensure_accounts();select settings into s from public.profiles where user_id=u;
 if payload?'timezone' then tz:=payload->>'timezone';if not exists(select 1 from pg_timezone_names where name=tz) then raise exception 'Invalid timezone' using errcode='22023';end if;end if;
 if payload?'theme' and payload->>'theme' not in ('dark','light','system') then raise exception 'Invalid theme' using errcode='22023';end if;
 if payload?'monthlyLimitCents' and payload->'monthlyLimitCents'<>'null'::jsonb and ((payload->>'monthlyLimitCents')::numeric not between 0 and 100000000000 or (payload->>'monthlyLimitCents')::numeric<>trunc((payload->>'monthlyLimitCents')::numeric)) then raise exception 'Invalid monthly limit' using errcode='22023';end if;
 if payload?'notifications' and (jsonb_typeof(payload->'notifications')<>'object' or exists(select 1 from jsonb_each(payload->'notifications') where jsonb_typeof(value)<>'boolean')) then raise exception 'Invalid notifications' using errcode='22023';end if;
 s:=s||(select coalesce(jsonb_object_agg(key,value),'{}'::jsonb) from jsonb_each(payload) where key in ('timezone','theme','monthlyLimitCents','notifications'));
 update public.profiles set settings=s,updated_at=now() where user_id=u;return s;end$$;

create function gridiron_private.ledger() returns jsonb language plpgsql security definer set search_path='' as $$
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
 'bets',(select coalesce(jsonb_agg(jsonb_build_object('id',id,'sportsbook',sportsbook,'event',event,'market',market,'selection',selection,'odds',odds,'stakeCents',stake_cents,'stake',(stake_cents/100)::numeric(20,2)::text,'placedAt',placed_at,'settledAt',settled_at,'result',result,'payoutCents',payout_cents,'payout',(payout_cents/100)::numeric(20,2)::text,'notes',notes,'prediction',prediction,'legs',legs) order by placed_at desc),'[]'::jsonb) from bet_rows),
 'summary',(select jsonb_build_object('cashBalanceCents',(select coalesce(sum(cash+escrow),0) from account_balances),'availableBalanceCents',(select coalesce(sum(cash),0) from account_balances),'pendingExposureCents',(select coalesce(sum(escrow),0) from account_balances),'realizedPlCents',t.profit,'totalDepositsCents',c.deposits,'totalWithdrawalsCents',c.withdrawals,'netCashContributedCents',c.starting+c.deposits-c.withdrawals,'settledStakeCents',t.settled_stake,'roi',t.profit/nullif(t.settled_stake,0),'averageStakeCents',t.average_stake,'largestWinCents',t.largest_win,'largestLossCents',t.largest_loss,'totalBets',t.total_bets,'settledBets',t.settled_bets) from capital c cross join totals t),
 'chart',(select coalesce(jsonb_agg(jsonb_build_object('date',bucket_date,'balanceCents',balance,'profitCents',profit) order by bucket_date),'[]'::jsonb) from running),
 'audit',(select coalesce(jsonb_agg(jsonb_build_object('action',action,'entityId',entity_id,'detail',detail,'createdAt',created_at) order by created_at desc),'[]'::jsonb) from (select * from public.audit_log where user_id=u order by created_at desc limit 200) x),
 'performanceByMarket',(select coalesce(jsonb_agg(x),'[]'::jsonb) from (select market,count(*) bets,sum(stake_cents) "stakeCents",sum(payout_cents-stake_cents) "profitCents",sum(payout_cents-stake_cents)/nullif(sum(stake_cents),0) roi from bet_rows where result not in ('pending','voided') group by market) x),
 'performanceBySportsbook',(select coalesce(jsonb_agg(x),'[]'::jsonb) from (select a.sportsbook,count(b.id) bets,coalesce(sum(b.stake_cents),0) "stakeCents",coalesce(sum(b.payout_cents-b.stake_cents),0) "profitCents",sum(b.payout_cents-b.stake_cents)/nullif(sum(b.stake_cents),0) roi from account_balances a left join bet_rows b on b.account_id=a.id and b.result not in ('pending','voided') group by a.sportsbook) x)
) into answer;return answer;end$$;

create function gridiron_private.consume_rate_limit(payload jsonb) returns jsonb language plpgsql security definer set search_path='' as $$declare u uuid:=gridiron_private.owner_id();k text:=payload->>'key';lim integer:=coalesce((payload->>'limit')::integer,60);seconds integer:=coalesce(ceil((payload->>'windowMs')::numeric/1000)::integer,(payload->>'windowSeconds')::integer,60);r public.rate_limit_buckets%rowtype;begin
 if length(k) not between 1 and 160 or lim not between 1 and 1000 or seconds not between 1 and 86400 then raise exception 'Invalid rate limit configuration' using errcode='22023';end if;seconds:=greatest(seconds,60);if k like 'simulations%' then seconds:=greatest(seconds,3600);end if;
 perform pg_advisory_xact_lock(hashtextextended(u::text||':'||k,0));select * into r from public.rate_limit_buckets where user_id=u and key=k;
 if found and r.reset_at>now() and r.count>=lim then raise exception 'Too many requests' using errcode='P0001';end if;
 insert into public.rate_limit_buckets(user_id,key,count,reset_at) values(u,k,1,now()+make_interval(secs=>seconds)) on conflict(user_id,key) do update set count=case when rate_limit_buckets.reset_at<=now() then 1 else rate_limit_buckets.count+1 end,reset_at=case when rate_limit_buckets.reset_at<=now() then excluded.reset_at else rate_limit_buckets.reset_at end;
 return jsonb_build_object('allowed',true);end$$;

create function gridiron_private.import_transactions(payload jsonb) returns jsonb language plpgsql security definer set search_path='' as $$declare u uuid:=gridiron_private.owner_id();row_data jsonb;idx integer:=0;imported integer:=0;skipped integer:=0;ref text;existing public.ledger_entries%rowtype;begin
 perform pg_advisory_xact_lock(hashtextextended(u::text,0));
 if jsonb_typeof(payload->'rows')<>'array' or jsonb_array_length(payload->'rows') not between 1 and 500 then raise exception 'Import 1-500 rows' using errcode='22023';end if;
 for row_data in select value from jsonb_array_elements(payload->'rows') loop
  idx:=idx+1;ref:=nullif(row_data->>'reference','');if ref is null and nullif(payload->>'importId','') is not null then ref:='import:'||left(payload->>'importId',100)||':'||idx;row_data:=row_data||jsonb_build_object('reference',ref);end if;
  if ref is not null then select * into existing from public.ledger_entries where user_id=u and reference=ref;
   if found then if existing.type<>row_data->>'type' or existing.amount_cents<>gridiron_private.amount(row_data->>'amount') then raise exception 'Import reference conflict; reconcile before retry' using errcode='23505';end if;skipped:=skipped+1;continue;end if;
  end if;
  perform gridiron_private.post_transaction(row_data);imported:=imported+1;
 end loop;return jsonb_build_object('imported',imported,'skipped',skipped,'message','Rows imported atomically; duplicate references skipped');end$$;

create function gridiron_private.reconcile(payload jsonb) returns jsonb language plpgsql security definer set search_path='' as $$declare u uuid:=gridiron_private.owner_id();a uuid;n numeric;b numeric;id_value uuid:=gen_random_uuid();begin
 a:=gridiron_private.account_id(payload->>'sportsbook');n:=gridiron_private.amount(payload->>'statementBalance',true);b:=gridiron_private.balance(a);
 insert into public.reconciliation_records(id,user_id,account_id,statement_balance_cents,recorded_balance_cents,difference_cents,note) values(id_value,u,a,n,b,n-b,coalesce(payload->>'note',''));
 insert into public.audit_log(user_id,action,entity_id,detail) values(u,'reconcile',id_value,payload);
 return jsonb_build_object('id',id_value,'sportsbook',payload->>'sportsbook','statementBalanceCents',n,'recordedBalanceCents',b,'differenceCents',n-b,'reconciled',n=b);end$$;

create function gridiron_private.delete_own_data() returns jsonb language plpgsql security definer set search_path='' as $$declare u uuid:=gridiron_private.owner_id();t text;begin
 perform pg_advisory_xact_lock(hashtextextended(u::text,0));
 -- Each owned FK is deferred/ordered through a single authenticated cleanup transaction.
 for t in select unnest(array['prediction_audits','calibration_metrics','probability_distributions','simulation_scenarios','paper_positions','model_predictions','backtests','simulation_runs','training_runs','feature_snapshots','model_versions','contract_outcomes','contract_quotes','market_contracts','market_events','market_providers','nfl_plays','team_statistics','player_statistics','player_usage','depth_charts','coaching_tendencies','injury_reports','weather_reports','nfl_games','nfl_players','nfl_teams','nfl_seasons','saved_reports','saved_research','watchlists','conversation_messages','conversations','gridiron_records','preferences','notification_settings','reconciliation_records','settlements','wager_legs','wagers','ledger_postings','ledger_entries','sportsbook_accounts','data_imports','rate_limit_buckets','audit_log','profiles']) loop execute format('delete from public.%I where user_id=$1',t) using u;end loop;
 return jsonb_build_object('deleted',true,'authAccountDeleted',false,'note','Application records deleted. Supabase Auth identity deletion requires an authorized administrator.');end$$;

-- Public wrappers are security invokers. Privilege is narrowly delegated to private,
-- auth.uid()-checked functions so clients cannot directly forge ledger postings.
create function public.gridiron_ledger() returns jsonb language sql security invoker set search_path='' as $$select gridiron_private.ledger()$$;
create function public.gridiron_post_transaction(payload jsonb) returns jsonb language sql security invoker set search_path='' as $$select gridiron_private.post_transaction(payload)$$;
create function public.gridiron_place_bet(payload jsonb) returns jsonb language sql security invoker set search_path='' as $$select gridiron_private.place_bet(payload)$$;
create function public.gridiron_settle_bet(payload jsonb) returns jsonb language sql security invoker set search_path='' as $$select gridiron_private.settle_bet(payload)$$;
create function public.gridiron_reverse_transaction(payload jsonb) returns jsonb language sql security invoker set search_path='' as $$select gridiron_private.reverse_transaction(payload)$$;
create function public.gridiron_update_settings(payload jsonb) returns jsonb language sql security invoker set search_path='' as $$select gridiron_private.update_settings(payload)$$;
create function public.gridiron_consume_rate_limit(payload jsonb) returns jsonb language sql security invoker set search_path='' as $$select gridiron_private.consume_rate_limit(payload)$$;
create function public.gridiron_import_transactions(payload jsonb) returns jsonb language sql security invoker set search_path='' as $$select gridiron_private.import_transactions(payload)$$;
create function public.gridiron_reconcile(payload jsonb) returns jsonb language sql security invoker set search_path='' as $$select gridiron_private.reconcile(payload)$$;
create function public.gridiron_delete_own_data() returns jsonb language sql security invoker set search_path='' as $$select gridiron_private.delete_own_data()$$;

revoke all on all functions in schema gridiron_private from public,anon,authenticated;
grant execute on function gridiron_private.ledger(),gridiron_private.post_transaction(jsonb),gridiron_private.place_bet(jsonb),gridiron_private.settle_bet(jsonb),gridiron_private.reverse_transaction(jsonb),gridiron_private.update_settings(jsonb),gridiron_private.consume_rate_limit(jsonb),gridiron_private.import_transactions(jsonb),gridiron_private.reconcile(jsonb),gridiron_private.delete_own_data() to authenticated;
revoke all on function public.gridiron_ledger(),public.gridiron_post_transaction(jsonb),public.gridiron_place_bet(jsonb),public.gridiron_settle_bet(jsonb),public.gridiron_reverse_transaction(jsonb),public.gridiron_update_settings(jsonb),public.gridiron_consume_rate_limit(jsonb),public.gridiron_import_transactions(jsonb),public.gridiron_reconcile(jsonb),public.gridiron_delete_own_data() from public,anon;
grant execute on function public.gridiron_ledger(),public.gridiron_post_transaction(jsonb),public.gridiron_place_bet(jsonb),public.gridiron_settle_bet(jsonb),public.gridiron_reverse_transaction(jsonb),public.gridiron_update_settings(jsonb),public.gridiron_consume_rate_limit(jsonb),public.gridiron_import_transactions(jsonb),public.gridiron_reconcile(jsonb),public.gridiron_delete_own_data() to authenticated;

-- Explicit, idempotent migration of a verified decrypted account export.
-- Imported authentication credentials/sessions are intentionally ignored.
create function gridiron_private.import_backup(payload jsonb,import_hash text) returns jsonb language plpgsql security definer set search_path='' as $$
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
   id_value:=coalesce(nullif(r->>'id','')::uuid,gen_random_uuid());
   parsed:=case when jsonb_typeof(r->'data')='string' then (r->>'data')::jsonb when r?'data' then r->'data' else r end;
   if table_name='simulation_jobs' then parsed:=jsonb_build_object('id',id_value,'kind',r->>'kind','status',r->>'status','data',parsed,'result',case when jsonb_typeof(r->'result')='string' then (r->>'result')::jsonb else r->'result' end,'error',r->>'error','createdAt',r->>'created_at','updatedAt',r->>'updated_at');
   elsif table_name='simulation_inputs' then parsed:=jsonb_build_object('jobId',r->>'job_id','input',parsed);
   else parsed:=parsed||jsonb_build_object('id',id_value,'createdAt',coalesce(r->>'created_at',now()::text));end if;
   insert into public.gridiron_records(id,user_id,kind,entity_key,data,source,observed_at,created_at,updated_at) values(id_value,u,table_name,coalesce(r->>'entity_key',r->>'contract_id',r->>'job_id',''),parsed,coalesce(r->>'source','verified account backup'),coalesce(nullif(r->>'observed_at','')::timestamptz,nullif(r->>'quoted_at','')::timestamptz,nullif(r->>'created_at','')::timestamptz,now()),coalesce(nullif(r->>'created_at','')::timestamptz,now()),coalesce(nullif(r->>'updated_at','')::timestamptz,nullif(r->>'created_at','')::timestamptz,now()));record_count:=record_count+1;
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
create function public.gridiron_import_backup(payload jsonb,import_hash text) returns jsonb language sql security invoker set search_path='' as $$select gridiron_private.import_backup(payload,import_hash)$$;
revoke all on function gridiron_private.import_backup(jsonb,text) from public,anon,authenticated;
grant execute on function gridiron_private.import_backup(jsonb,text) to authenticated;
revoke all on function public.gridiron_import_backup(jsonb,text) from public,anon;
grant execute on function public.gridiron_import_backup(jsonb,text) to authenticated;

-- Index each referencing key tuple, in addition to owner/time access paths.
do $$declare r record;cols text;begin
 for r in select c.oid,c.conrelid,n.nspname,t.relname,c.conkey from pg_constraint c join pg_class t on t.oid=c.conrelid join pg_namespace n on n.oid=t.relnamespace where c.contype='f' and n.nspname='public' loop
  select string_agg(quote_ident(a.attname),',' order by k.ordinality) into cols from unnest(r.conkey) with ordinality k(attnum,ordinality) join pg_attribute a on a.attrelid=r.conrelid and a.attnum=k.attnum;
  execute format('create index if not exists %I on %I.%I(%s)','gridiron_fk_'||r.oid,r.nspname,r.relname,cols);
 end loop;
end$$;
