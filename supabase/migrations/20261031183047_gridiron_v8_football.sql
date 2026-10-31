-- Additive NFL/CFB expansion. No existing account, ledger, prediction or source is reset.
-- Public data admission retains the existing450MB reserve. Only tiny compute
-- reservation metadata may be written above it, under the existing500k UTC pool.
create table public.football_data_sources(
 id text primary key check(length(id) between 1 and 500),sport text not null check(sport in ('NFL','CFB')),
 provider text not null check(provider in ('ESPN','SportsDataverse','CollegeFootballData','BallDontLie','DraftKings Predictions','Kalshi')),
 source_url text not null check(source_url ~ '^https://[^[:space:]]+$' and source_url !~* '[?&](api_?key|token|access_token|password)=|https://[^/]+@'),
 collected_at timestamptz not null,available_at timestamptz,event_time timestamptz,source_version text not null,
 reliability text not null check(reliability in ('verified','partial','unavailable')),data jsonb not null default '{}'::jsonb check(jsonb_typeof(data)='object'),
 created_at timestamptz not null default now(),updated_at timestamptz not null default now(),unique(id,sport)
);

create table public.cfb_conferences(id text primary key check(id like 'cfb:%'),sport text not null default 'CFB' check(sport='CFB'),provider_id text not null,name text,source_id text not null,source_version text not null check(length(source_version) between 1 and 200),collected_at timestamptz not null,available_at timestamptz,event_time timestamptz,reliability text not null check(reliability in ('verified','partial','unavailable')),data jsonb not null default '{}'::jsonb check(jsonb_typeof(data)='object'),created_at timestamptz not null default now(),updated_at timestamptz not null default now(),foreign key(source_id,sport) references public.football_data_sources(id,sport));

create table public.cfb_teams(id text primary key check(id like 'cfb:%'),sport text not null default 'CFB' check(sport='CFB'),provider_id text not null,name text not null,abbreviation text,conference_id text references public.cfb_conferences(id),classification text check(classification in ('fbs','fcs','ii','iii','unknown')),source_id text not null,source_version text not null check(length(source_version) between 1 and 200),collected_at timestamptz not null,available_at timestamptz,event_time timestamptz,reliability text not null check(reliability in ('verified','partial','unavailable')),data jsonb not null default '{}'::jsonb check(jsonb_typeof(data)='object'),created_at timestamptz not null default now(),updated_at timestamptz not null default now(),foreign key(source_id,sport) references public.football_data_sources(id,sport));

create table public.cfb_players(id text primary key check(id like 'cfb:%'),sport text not null default 'CFB' check(sport='CFB'),provider_id text not null,name text not null,team_id text references public.cfb_teams(id),position text,source_id text not null,source_version text not null check(length(source_version) between 1 and 200),collected_at timestamptz not null,available_at timestamptz,event_time timestamptz,reliability text not null check(reliability in ('verified','partial','unavailable')),data jsonb not null default '{}'::jsonb check(jsonb_typeof(data)='object'),created_at timestamptz not null default now(),updated_at timestamptz not null default now(),foreign key(source_id,sport) references public.football_data_sources(id,sport));

create table public.cfb_games(id text primary key check(id like 'cfb:%'),sport text not null default 'CFB' check(sport='CFB'),provider_id text not null,season integer not null check(season between 2000 and 2100),week integer check(week between 1 and 30),home_team_id text not null references public.cfb_teams(id),away_team_id text not null references public.cfb_teams(id),kickoff_at timestamptz not null,kickoff_verified boolean not null default false,status text not null check(status in ('scheduled','live','final','postponed','cancelled')),check(home_team_id<>away_team_id),source_id text not null,source_version text not null check(length(source_version) between 1 and 200),collected_at timestamptz not null,available_at timestamptz,event_time timestamptz,reliability text not null check(reliability in ('verified','partial','unavailable')),data jsonb not null default '{}'::jsonb check(jsonb_typeof(data)='object'),created_at timestamptz not null default now(),updated_at timestamptz not null default now(),foreign key(source_id,sport) references public.football_data_sources(id,sport));

create table public.cfb_plays(id text primary key check(id like 'cfb:%'),sport text not null default 'CFB' check(sport='CFB'),game_id text not null references public.cfb_games(id),source_play_id text not null,offense_team_id text references public.cfb_teams(id),defense_team_id text references public.cfb_teams(id),passer_id text references public.cfb_players(id),receiver_id text references public.cfb_players(id),rusher_id text references public.cfb_players(id),down integer check(down between 1 and 4),distance numeric,seconds_remaining integer check(seconds_remaining between 0 and 3600),source_id text not null,source_version text not null check(length(source_version) between 1 and 200),collected_at timestamptz not null,available_at timestamptz,event_time timestamptz,reliability text not null check(reliability in ('verified','partial','unavailable')),data jsonb not null default '{}'::jsonb check(jsonb_typeof(data)='object'),created_at timestamptz not null default now(),updated_at timestamptz not null default now(),foreign key(source_id,sport) references public.football_data_sources(id,sport));

create table public.cfb_team_statistics(id text primary key check(id like 'cfb:%'),sport text not null default 'CFB' check(sport='CFB'),team_id text not null references public.cfb_teams(id),game_id text references public.cfb_games(id),season integer not null check(season between 2000 and 2100),metric text not null,value numeric,source_id text not null,source_version text not null check(length(source_version) between 1 and 200),collected_at timestamptz not null,available_at timestamptz,event_time timestamptz,reliability text not null check(reliability in ('verified','partial','unavailable')),data jsonb not null default '{}'::jsonb check(jsonb_typeof(data)='object'),created_at timestamptz not null default now(),updated_at timestamptz not null default now(),foreign key(source_id,sport) references public.football_data_sources(id,sport));

create table public.cfb_player_statistics(id text primary key check(id like 'cfb:%'),sport text not null default 'CFB' check(sport='CFB'),player_id text not null references public.cfb_players(id),game_id text references public.cfb_games(id),season integer not null check(season between 2000 and 2100),metric text not null,value numeric,source_id text not null,source_version text not null check(length(source_version) between 1 and 200),collected_at timestamptz not null,available_at timestamptz,event_time timestamptz,reliability text not null check(reliability in ('verified','partial','unavailable')),data jsonb not null default '{}'::jsonb check(jsonb_typeof(data)='object'),created_at timestamptz not null default now(),updated_at timestamptz not null default now(),foreign key(source_id,sport) references public.football_data_sources(id,sport));

create table public.cfb_injuries(id text primary key check(id like 'cfb:%'),sport text not null default 'CFB' check(sport='CFB'),player_id text references public.cfb_players(id),player_name text not null,team_id text not null references public.cfb_teams(id),game_id text references public.cfb_games(id),status text not null,practice_participation text,availability text not null check(availability in ('unknown','uncertain','confirmed_active','confirmed_inactive')),official_confirmed boolean not null default false,source_id text not null,source_version text not null check(length(source_version) between 1 and 200),collected_at timestamptz not null,available_at timestamptz,event_time timestamptz,reliability text not null check(reliability in ('verified','partial','unavailable')),data jsonb not null default '{}'::jsonb check(jsonb_typeof(data)='object'),created_at timestamptz not null default now(),updated_at timestamptz not null default now(),foreign key(source_id,sport) references public.football_data_sources(id,sport));

create table public.cfb_rankings(id text primary key check(id like 'cfb:%'),sport text not null default 'CFB' check(sport='CFB'),team_id text not null references public.cfb_teams(id),season integer not null check(season between 2000 and 2100),week integer,poll text not null,rank integer check(rank between 1 and 200),source_id text not null,source_version text not null check(length(source_version) between 1 and 200),collected_at timestamptz not null,available_at timestamptz,event_time timestamptz,reliability text not null check(reliability in ('verified','partial','unavailable')),data jsonb not null default '{}'::jsonb check(jsonb_typeof(data)='object'),created_at timestamptz not null default now(),updated_at timestamptz not null default now(),foreign key(source_id,sport) references public.football_data_sources(id,sport));

create table public.cfb_depth_charts(id text primary key check(id like 'cfb:%'),sport text not null default 'CFB' check(sport='CFB'),team_id text not null references public.cfb_teams(id),player_id text references public.cfb_players(id),position text not null,depth integer check(depth between 1 and 30),source_id text not null,source_version text not null check(length(source_version) between 1 and 200),collected_at timestamptz not null,available_at timestamptz,event_time timestamptz,reliability text not null check(reliability in ('verified','partial','unavailable')),data jsonb not null default '{}'::jsonb check(jsonb_typeof(data)='object'),created_at timestamptz not null default now(),updated_at timestamptz not null default now(),foreign key(source_id,sport) references public.football_data_sources(id,sport));

create table public.cfb_model_versions(id text primary key check(id like 'cfb:%'),sport text not null default 'CFB' check(sport='CFB'),model_version text not null,model_kind text not null check(model_kind in ('game','player','calibration')),approval_status text not null check(approval_status in ('candidate','approved','retired')),unique(id,approval_status),source_id text not null,source_version text not null check(length(source_version) between 1 and 200),collected_at timestamptz not null,available_at timestamptz,event_time timestamptz,reliability text not null check(reliability in ('verified','partial','unavailable')),data jsonb not null default '{}'::jsonb check(jsonb_typeof(data)='object'),created_at timestamptz not null default now(),updated_at timestamptz not null default now(),foreign key(source_id,sport) references public.football_data_sources(id,sport));


create table public.shared_cfb_cache(kind text not null,key text not null,sport text not null default 'CFB' check(sport='CFB'),data jsonb not null check(jsonb_typeof(data)='object'),input_hash text not null,updated_at timestamptz not null default now(),expires_at timestamptz not null,primary key(kind,key));
create table public.provider_market_quotes(
 id text primary key check(length(id) between 1 and 500),sport text not null check(sport in ('NFL','CFB')),
 provider text not null check(provider in ('BallDontLie','CollegeFootballData','DraftKings Predictions','Kalshi')),
 market_family text not null check(market_family in ('sportsbook_reference','event_contract')),event_id text not null,market_id text not null,selection text not null,line numeric(20,6),american_odds integer check(abs(american_odds) between 100 and 100000),bid_cents numeric(20,6) check(bid_cents between 0 and 100),ask_cents numeric(20,6) check(ask_cents between 0 and 100),quoted_at timestamptz,observed_at timestamptz not null,
 source_url text not null check(source_url ~ '^https://[^[:space:]]+$' and source_url !~* '[?&](api_?key|token|access_token|password)=|https://[^/]+@'),data jsonb not null check(jsonb_typeof(data)='object'),created_at timestamptz not null default now(),
 check((market_family='sportsbook_reference' and american_odds is not null and bid_cents is null and ask_cents is null) or(market_family='event_contract' and american_odds is null)),
 check(provider<>'BallDontLie' or(sport='NFL' and market_family='sportsbook_reference')),
 check(provider<>'CollegeFootballData' or(sport='CFB' and market_family='sportsbook_reference')),
 check(provider not in('DraftKings Predictions','Kalshi') or market_family='event_contract'),check(quoted_at is null or quoted_at<=observed_at+interval '1 minute')
);
create index provider_market_quotes_event_time on public.provider_market_quotes(sport,provider,event_id,observed_at desc);
create index cfb_games_kickoff on public.cfb_games(kickoff_at);
create index cfb_players_team on public.cfb_players(team_id);
create index cfb_team_statistics_scope on public.cfb_team_statistics(team_id,season,metric);
create index cfb_player_statistics_scope on public.cfb_player_statistics(player_id,season,metric);
create index cfb_injuries_team_time on public.cfb_injuries(team_id,collected_at desc);
create index cfb_plays_game on public.cfb_plays(game_id);

create table public.cfb_simulation_runs(
 id uuid primary key,user_id uuid not null default auth.uid() references auth.users(id) on delete cascade,record_id uuid not null,event_key text not null check(event_key like 'cfb:%'),game_id text references public.cfb_games(id),sport text not null default 'CFB' check(sport='CFB'),model_version text not null,input_version text not null,simulations integer not null check(simulations in(10000,50000,100000)),event_start timestamptz not null,created_at timestamptz not null default now(),unique(id,user_id),foreign key(record_id,user_id) references public.gridiron_records(id,user_id) on delete cascade
);
create index cfb_simulation_runs_owner on public.cfb_simulation_runs(user_id,created_at desc);
create table public.cfb_prediction_snapshots(
 id uuid primary key default gen_random_uuid(),user_id uuid not null default auth.uid() references auth.users(id) on delete cascade,simulation_id uuid not null,event_key text not null check(event_key like 'cfb:%'),sport text not null default 'CFB' check(sport='CFB'),market text not null,threshold numeric,raw_probability numeric not null check(raw_probability between 0 and 1),calibrated_probability numeric check(calibrated_probability between 0 and 1),calibration_artifact_id text,calibration_status text check(calibration_status='approved'),captured_at timestamptz not null,event_start timestamptz not null,data jsonb not null check(jsonb_typeof(data)='object'),created_at timestamptz not null default now(),foreign key(simulation_id,user_id) references public.cfb_simulation_runs(id,user_id) on delete cascade,foreign key(calibration_artifact_id,calibration_status) references public.cfb_model_versions(id,approval_status),check(captured_at<event_start),check(created_at<event_start),check(calibrated_probability is null or(calibration_artifact_id is not null and calibration_status='approved'))
);
create index cfb_prediction_snapshots_owner on public.cfb_prediction_snapshots(user_id,event_start);

do $security$declare t text;begin
 foreach t in array array['football_data_sources','cfb_conferences','cfb_teams','cfb_players','cfb_games','cfb_plays','cfb_team_statistics','cfb_player_statistics','cfb_injuries','cfb_rankings','cfb_depth_charts','cfb_model_versions','shared_cfb_cache','provider_market_quotes'] loop
  execute format('alter table public.%I enable row level security',t);execute format('revoke all on public.%I from public,anon,authenticated',t);execute format('grant select on public.%I to anon,authenticated',t);execute format('create policy %I on public.%I for select to anon,authenticated using(true)',t||'_public_read',t);
 end loop;
 foreach t in array array['cfb_simulation_runs','cfb_prediction_snapshots'] loop
  execute format('alter table public.%I enable row level security',t);execute format('revoke all on public.%I from public,anon,authenticated',t);execute format('grant select,insert on public.%I to authenticated',t);execute format('create policy %I on public.%I for select to authenticated using((select auth.uid())=user_id)',t||'_owner_read',t);execute format('create policy %I on public.%I for insert to authenticated with check((select auth.uid())=user_id)',t||'_owner_insert',t);
 end loop;
end $security$;
create trigger provider_market_quotes_immutable before update or delete on public.provider_market_quotes for each row execute function gridiron_shared_private.prop_immutable();
create trigger cfb_prediction_snapshots_immutable before update on public.cfb_prediction_snapshots for each row execute function gridiron_private.immutable_row();
create trigger cfb_simulation_runs_immutable before update on public.cfb_simulation_runs for each row execute function gridiron_private.immutable_row();

create table gridiron_shared_private.cfb_compute_reservations(
 id uuid primary key default gen_random_uuid(),day date not null,input_hash text not null check(input_hash ~ '^[a-f0-9]{64}$'),simulations integer not null check(simulations in(10000,50000,100000)),status text not null default 'running' check(status in('running','completed','failed')),lease uuid not null,created_at timestamptz not null default now(),updated_at timestamptz not null default now(),unique(day,input_hash,simulations)
);
alter table gridiron_shared_private.cfb_compute_reservations enable row level security;
revoke all on gridiron_shared_private.cfb_compute_reservations from public,anon,authenticated;
create policy cfb_compute_no_client_access on gridiron_shared_private.cfb_compute_reservations for all to anon,authenticated using(false) with check(false);

create function gridiron_shared_private.football_data_write_operation(token text,payload jsonb) returns jsonb
language plpgsql security definer set search_path='' as $function$
declare action text:=payload->>'action';item jsonb;q jsonb;source_row jsonb;output jsonb:='[]'::jsonb;table_name text;answer jsonb;today date:=(now() at time zone 'UTC')::date;requested integer;used integer;reserved gridiron_shared_private.cfb_compute_reservations;existing jsonb;
begin
 if not gridiron_shared_private.valid_public_capability(token) then raise exception 'Server capability required' using errcode='42501';end if;
 if payload is null or jsonb_typeof(payload)<>'object' or octet_length(payload::text)>4000000 then raise exception 'Bounded football JSON operation required' using errcode='22023';end if;
 if action='status' then return jsonb_build_object('admissionAvailable',gridiron_shared_private.has_public_storage_headroom());end if;
 if action='reserve_compute' then
  if exists(select 1 from jsonb_object_keys(payload) k where k not in('action','inputHash','simulations','lease')) then raise exception 'CFB compute reservation accepts metadata only' using errcode='22023';end if;
  requested:=(payload->>'simulations')::integer;
  if requested is null or requested not in(10000,50000,100000) or payload->>'inputHash' is null or payload->>'inputHash' !~ '^[a-f0-9]{64}$' or nullif(payload->>'lease','') is null then raise exception 'Exact CFB model-input identity, supported count and worker lease required' using errcode='22023';end if;
  perform pg_advisory_xact_lock(hashtextextended('gridiron-public-complete-game-budget',0));
  select * into reserved from gridiron_shared_private.cfb_compute_reservations where day=today and input_hash=payload->>'inputHash' and simulations=requested;
  if reserved.id is not null then return jsonb_build_object('id',reserved.id,'execute',false,'duplicate',true,'status',reserved.status);end if;
  insert into gridiron_shared_private.compute_budget(day,games) values(today,0) on conflict(day) do nothing;
  select games into used from gridiron_shared_private.compute_budget where day=today for update;
  if used+requested>500000 then raise exception 'Daily shared complete-game research capacity is reached. Saved results remain available.' using errcode='54000';end if;
  insert into gridiron_shared_private.cfb_compute_reservations(day,input_hash,simulations,lease)values(today,payload->>'inputHash',requested,(payload->>'lease')::uuid) returning * into reserved;
  update gridiron_shared_private.compute_budget set games=games+requested where day=today;
  return jsonb_build_object('id',reserved.id,'execute',true,'duplicate',false,'status','running');
 elsif action='complete_compute' or action='fail_compute' then
  if exists(select 1 from jsonb_object_keys(payload) k where k not in('action','id','lease')) then raise exception 'CFB compute checkpoints accept metadata only' using errcode='22023';end if;
  update gridiron_shared_private.cfb_compute_reservations set status=case when action='complete_compute' then 'completed' else 'failed' end,updated_at=now() where id=(payload->>'id')::uuid and status='running' and lease=(payload->>'lease')::uuid returning * into reserved;
  if reserved.id is null then raise exception 'Stale CFB compute lease' using errcode='40001';end if;return jsonb_build_object('id',reserved.id,'status',reserved.status);
 end if;
 if not gridiron_shared_private.has_public_storage_headroom() then raise exception 'New public football data persistence is paused to protect personal records. Existing history is preserved.' using errcode='54000';end if;
 if action='batch' then
  if jsonb_typeof(payload->'operations') is distinct from 'array' or jsonb_array_length(payload->'operations') not between 1 and 100 then raise exception 'Use1–100 bounded operations' using errcode='22023';end if;
  for item in select value from jsonb_array_elements(payload->'operations') loop
   if item->>'action' in('batch','reserve_compute','complete_compute','fail_compute','status') then raise exception 'Nested control operations are not supported' using errcode='22023';end if;
   output:=output||jsonb_build_array(gridiron_shared_private.football_data_write_operation(token,item));
  end loop;return output;
 elsif action='provider_quote_put' then
  q:=payload->'quote';
  if jsonb_typeof(q) is distinct from 'object' or octet_length(q::text)>32768 or q::text ~* '"(api_?key|authorization|access_token|refresh_token|service_role_key|password|user_id|userId|bankroll|deposits|withdrawals)"[[:space:]]*:' then raise exception 'A bounded secret-free provider quote is required' using errcode='22023';end if;
  if nullif(q->>'id','') is null or nullif(q->>'eventId','') is null or nullif(q->>'marketId','') is null or nullif(q->>'selection','') is null or (q->>'observedAt')::timestamptz>now()+interval '1 minute' then raise exception 'Exact event/market/selection and observation required' using errcode='22023';end if;
  if nullif(q->>'line','') is not null and q->>'line' !~ '^-?[0-9]{1,12}(\.[0-9]{1,6})?$' then raise exception 'A finite exact market threshold is required' using errcode='22023';end if;
  select to_jsonb(t) into existing from public.provider_market_quotes t where id=q->>'id';
  if existing is not null then
   if existing->>'sport' is distinct from q->>'sport' or existing->>'provider' is distinct from q->>'provider' or existing->>'market_family' is distinct from q->>'marketFamily' or existing->>'event_id' is distinct from q->>'eventId' or existing->>'market_id' is distinct from q->>'marketId' or existing->>'selection' is distinct from q->>'selection' or nullif(existing->>'line','')::numeric is distinct from nullif(q->>'line','')::numeric or nullif(existing->>'american_odds','')::integer is distinct from nullif(q->>'americanOdds','')::integer or nullif(existing->>'bid_cents','')::numeric is distinct from nullif(q->>'bidCents','')::numeric or nullif(existing->>'ask_cents','')::numeric is distinct from nullif(q->>'askCents','')::numeric or existing->>'source_url' is distinct from q->>'sourceUrl' or existing#>'{data,rulesHash}' is distinct from q#>'{data,rulesHash}' or existing#>'{data,settlement}' is distinct from q#>'{data,settlement}' or existing#>'{data,settlementRules}' is distinct from q#>'{data,settlementRules}' then raise exception 'An immutable provider quote ID cannot change sport, market identity, rules or price' using errcode='22023';end if;
   return existing;
  end if;
  insert into public.provider_market_quotes(id,sport,provider,market_family,event_id,market_id,selection,line,american_odds,bid_cents,ask_cents,quoted_at,observed_at,source_url,data)
   values(q->>'id',q->>'sport',q->>'provider',q->>'marketFamily',q->>'eventId',q->>'marketId',q->>'selection',nullif(q->>'line','')::numeric,nullif(q->>'americanOdds','')::integer,nullif(q->>'bidCents','')::numeric,nullif(q->>'askCents','')::numeric,nullif(q->>'quotedAt','')::timestamptz,(q->>'observedAt')::timestamptz,q->>'sourceUrl',coalesce(q->'data','{}')) on conflict(id) do nothing;
  select to_jsonb(t) into answer from public.provider_market_quotes t where id=q->>'id';return answer;
 elsif action='source_put' or action='entity_put' then
  table_name:=case when action='source_put' then 'football_data_sources' else payload->>'table' end;
  if table_name is null or table_name not in('football_data_sources','cfb_conferences','cfb_teams','cfb_players','cfb_games','cfb_plays','cfb_team_statistics','cfb_player_statistics','cfb_injuries','cfb_rankings','cfb_depth_charts','cfb_model_versions') then raise exception 'A supported CFB warehouse family is required' using errcode='22023';end if;
  source_row:=payload->'row';if jsonb_typeof(source_row) is distinct from 'object' or octet_length(source_row::text)>1000000 or source_row::text ~* '"(api_?key|authorization|access_token|refresh_token|service_role_key|password|user_id|userId|bankroll|deposits|withdrawals)"[[:space:]]*:' then raise exception 'A bounded versioned source/entity row is required' using errcode='22023';end if;
  source_row:=jsonb_build_object('sport','CFB','data','{}'::jsonb,'reliability','partial','collected_at',now())||source_row;
  execute format('select to_jsonb(t) from public.%I t where id=$1',table_name)using source_row->>'id' into existing;
  if existing is not null then
   execute format('select to_jsonb(jsonb_populate_record(null::public.%I,$1))',table_name)using source_row into answer;
   if existing-'created_at'-'updated_at'-'collected_at' is distinct from answer-'created_at'-'updated_at'-'collected_at' then raise exception 'A versioned source/entity ID cannot overwrite existing historical content; append a new source version' using errcode='22023';end if;
   return existing;
  end if;
  execute format('insert into public.%I select (jsonb_populate_record(null::public.%I,$1)).* on conflict(id) do nothing returning to_jsonb(%I)',table_name,table_name,table_name) using source_row||jsonb_build_object('created_at',now(),'updated_at',now()) into answer;
  if answer is null then execute format('select to_jsonb(t) from public.%I t where id=$1',table_name)using source_row->>'id' into answer;end if;return answer;
 elsif action='cache_put' then
  if jsonb_typeof(payload->'data') is distinct from 'object' or payload->'data'->>'sport' is distinct from 'CFB' or (payload->'data')::text ~* '"(api_?key|authorization|access_token|refresh_token|service_role_key|password|user_id|userId|bankroll|deposits|withdrawals)"[[:space:]]*:' or octet_length((payload->'data')::text)>2000000 or length(payload->>'kind') not between 1 and 40 or length(payload->>'key') not between 1 and 250 then raise exception 'A bounded CFB-only public cache is required' using errcode='22023';end if;
  insert into public.shared_cfb_cache(kind,key,data,input_hash,expires_at)values(payload->>'kind',payload->>'key',payload->'data',payload->>'inputHash',(payload->>'expiresAt')::timestamptz)on conflict(kind,key) do update set data=excluded.data,input_hash=excluded.input_hash,expires_at=excluded.expires_at,updated_at=now() returning to_jsonb(shared_cfb_cache) into answer;return answer;
 end if;
 raise exception 'Unsupported football data operation' using errcode='22023';
end $function$;
revoke all on function gridiron_shared_private.football_data_write_operation(text,jsonb) from public,anon,authenticated;
grant execute on function gridiron_shared_private.football_data_write_operation(text,jsonb) to anon,authenticated;
create function public.gridiron_football_data_write(token text,payload jsonb) returns jsonb language sql security invoker set search_path='' as $$select gridiron_shared_private.football_data_write_operation(token,payload)$$;
revoke all on function public.gridiron_football_data_write(text,jsonb) from public;
grant execute on function public.gridiron_football_data_write(text,jsonb) to anon,authenticated;

-- Audited wallet metadata patch; amounts and historical predictions unchanged.
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
